"""Workchain to compute the X-ray photoelectron spectroscopy (XPS) for a given structure.

Uses QuantumESPRESSO pw.x.
"""
import pathlib
from typing import Optional, Union

import yaml
from aiida import orm
from aiida.common import AttributeDict, ValidationError
from aiida.engine import ToContext, WorkChain, if_
from aiida.orm.nodes.data.base import to_aiida_type
from aiida.plugins import CalculationFactory, DataFactory, WorkflowFactory
from aiida_pseudo.data.pseudo import UpfData
from aiida_qe_xspec.calculations.functions.xspectra.get_xps_spectra import get_spectra_by_element
from aiida_quantumespresso.utils.mapping import prepare_process_inputs
from aiida_quantumespresso.workflows.protocols.utils import ProtocolMixin, recursive_merge

PwCalculation = CalculationFactory('quantumespresso.pw')
PwBaseWorkChain = WorkflowFactory('quantumespresso.pw.base')
PwRelaxWorkChain = WorkflowFactory('quantumespresso.pw.relax')
XyData = DataFactory('core.array.xy')


def validate_inputs(inputs, _):
    """Validate the inputs before launching the WorkChain."""
    structure = inputs['structure']
    elements_present = {kind.symbol for kind in structure.kinds}
    abs_atom_marker = inputs['abs_atom_marker'].value
    core_hole_pseudos = inputs['core_hole_pseudos']
    if abs_atom_marker in elements_present:
        raise ValidationError(
            f'The marker given for the absorbing atom ("{abs_atom_marker}") matches an existing Kind in the '
            f'input structure ({elements_present}).'
        )
    if 'core_levels' in inputs:
        # keys of core_levels should be a subset of the structure elements and core_hole_pseudos
        core_levels = inputs['core_levels'].get_dict()
        if not set(core_levels.keys()).issubset(elements_present):
            elements_not_present = set(core_levels.keys()) - elements_present
            raise ValidationError(
                f'The following elements: {elements_not_present} are not present in the'
                f' structure ({elements_present}) provided.'
            )
        if not set(core_levels.keys()).issubset(set(core_hole_pseudos.keys())):
            elements_not_present = set(core_levels.keys()) - set(core_hole_pseudos.keys())
            raise ValidationError(
                f'The following elements: {elements_not_present} are required for analysis but '
                f'their pseudopotentials are not provided.'
            )
    if 'atom_indices' in inputs:
        # indices should be in the range of the number of atoms in the structure
        if not all(0 <= index < len(structure.sites) for index in inputs['atom_indices'].get_list()):
            raise ValidationError('All atom indices must be within the range of the number of atoms in the structure.')
        # all the elements corresponding to the atom indices should be in the core_hole_pseudos
        elements = {structure.get_kind(structure.sites[i].kind_name).symbol for i in inputs['atom_indices'].get_list()}
        if not elements.issubset(set(core_hole_pseudos.keys())):
            elements_not_present = elements - set(core_hole_pseudos.keys())
            raise ValidationError(
                f'The following elements: {elements_not_present} are required for analysis but'
                f' their pseudopotentials are not provided.'
            )

    if inputs['calc_binding_energy'].value:
        elements1 = set(inputs['core_levels'].keys())
        elements2 = set(inputs['correction_energies'].get_dict().keys())
        if elements1 != elements2:
            raise ValidationError(
                f'The ``correction_energies`` provided ({elements1}) does not match the list of'
                f' absorbing elements ({elements2})'
            )

class XpsWorkChain(ProtocolMixin, WorkChain):
    """Workchain to compute X-ray photoelectron spectra (XPS) for a given structure.

    The WorkChain itself firstly calls the PwRelaxWorkChain to relax the input structure if
    required. Then determines the input settings for each XPS calculation automatically using
    ``get_xspectra_structures()``. The input structures are generated from the standardized
    structure by converting each to a supercell with cell dimensions of at least 8.0 angstrom
    in each periodic dimension in order to sufficiently reduce the unphysical interaction
    of the core-hole with neighbouring images. The size of the minimum size requirement can be
    overriden by the user if required. Then the standard Delta-Self-Consistent-Field (ΔSCF)
    method is used to get the XPS binding energy. Finally, the XPS spectrum is calculated
    using the Voigt profile.

    """

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        # yapf: disable
        spec.expose_inputs(
            PwRelaxWorkChain,
            namespace='relax',
            exclude=('structure', 'clean_workdir', 'base_final_scf'),
            namespace_options={
                'help': (
                    'Input parameters for the relax process. If not specified at all, the relaxation step is skipped.'
                ),
                'required' : False,
                'populate_defaults' : False,
            }
        )
        spec.expose_inputs(
            PwBaseWorkChain,
            namespace='ch_scf',
            exclude=('pw.structure', ),
            namespace_options={
                'help': ('Input parameters for the basic xps workflow (core-hole SCF).'),
                'validator': None
            }
        )
        spec.input_namespace(
            'core_hole_pseudos',
            valid_type=(orm.UpfData, UpfData),
            dynamic=True,
            help=(
                'Dynamic namespace for pairs of excited-state pseudopotentials for each absorbing'
                ' element. Must use the mapping "{element}" : {Upf}".'
            )
        )
        spec.input(
            'core_hole_treatments',
            valid_type=orm.Dict,
            required=False,
            help=('Optional dictionary to set core-hole treatment to all elements present. '
                  'The default full-core-hole treatment will be used if not specified.'
                 )
        )
        spec.input(
            'structure',
            valid_type=orm.StructureData,
            help=(
                'Structure to be used for calculation.'
            )
        )
        spec.input(
            'voight_gamma',
            valid_type=orm.Float,
            default=lambda: orm.Float(0.3),
            help=(
                'The gamma parameter for the Lorenzian broadening in the Voight method.'
            )
        )
        spec.input(
            'voight_sigma',
            valid_type=orm.Float,
            default=lambda: orm.Float(0.3),
            help=(
                'The sigma parameter for the gaussian broadening in the Voight method.'
            )
        )
        spec.input(
            'abs_atom_marker',
            valid_type=orm.Str,
            default=lambda: orm.Str('X'),
            help=(
                'The name for the Kind representing the absorbing atom in the structure. '
                'Will be used in all structures generated in ``get_xspectra_structures`` step.'
            ),
        )
        spec.input_namespace(
            'structure_preparation_settings',
            valid_type=(orm.Dict, orm.Float, orm.Int, orm.Bool, orm.Str),
            dynamic=True,
            required=False,
            help=(
                'Optional settings dictionary for the ``get_xspectra_structures()`` method.'
            )
        )
        spec.input(
            'spglib_settings',
            valid_type=orm.Dict,
            required=False,
            help=(
                'Optional settings dictionary for the spglib call within ``get_xspectra_structures``.'
            )
        )
        spec.input(
            'core_levels',
            valid_type=orm.Dict,
            required=False,
            help=(
            'The elements and their core-levels to be considered for analysis. The element symbol must be valid elements of the periodic table.'
            )
        )
        spec.input(
            'atom_indices',
            valid_type=orm.List,
            required=False,
            help=(
            'The indices of atoms to be considered for analysis.'
            )
        )
        spec.input(
            'calc_binding_energy',
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help=('If `True`, run scf calculation for the supercell.'),
        )
        spec.input(
            'correction_energies',
            valid_type=orm.Dict,
            required=False,
            help=('Optional dictionary to set the correction energy to all elements present. '
                 )
        )
        spec.input(
            'clean_workdir',
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help=('If `True`, work directories of all called calculations will be cleaned at the end of execution.'),
        )
        spec.input(
            'dry_run',
            valid_type=orm.Bool,
            serializer=to_aiida_type,
            required=False,
            help='Terminate workchain steps before submitting calculations (test purposes only).'
        )
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.setup,
            if_(cls.should_run_relax)(
                cls.run_relax,
                cls.inspect_relax,
            ),
            cls.prepare_structures,
            cls.run_all_scf,
            cls.inspect_all_scf,
            cls.results,
        )

        spec.exit_code(401, 'ERROR_SUB_PROCESS_FAILED_RELAX', message='The Relax sub process failed')
        spec.exit_code(402, 'ERROR_SUB_PROCESS_FAILED_SCF', message='The SCF Pw sub processes failed')
        spec.exit_code(402, 'ERROR_SUB_PROCESS_FAILED_CH_SCF', message='One or more CH_SCF Pw sub processes failed')
        spec.output(
            'optimized_structure',
            valid_type=orm.StructureData,
            required=False,
            help='The optimized structure from the ``relax`` process.',
        )
        spec.output(
            'output_parameters_relax',
            valid_type=orm.Dict,
            required=False,
            help='The output_parameters of the relax step.'
        )
        spec.output(
            'standardized_structure',
            valid_type=orm.StructureData,
            required=False,
            help='The standardized crystal structure used to generate structures for XPS sub-processes.',
        )
        spec.output(
            'supercell_structure',
            valid_type=orm.StructureData,
            required=False,
            help=('The supercell of ``outputs.standardized_structure`` used to generate structures for'
            ' XPS sub-processes.')
        )
        spec.output(
            'symmetry_analysis_data',
            valid_type=orm.Dict,
            required=False,
            help='The output parameters from ``get_xspectra_structures()``.'
        )
        spec.output(
            'output_parameters_scf',
            valid_type=orm.Dict,
            required=False,
            help='The output_parameters of the scf step.'
        )
        spec.output_namespace(
            'output_parameters_ch_scf',
            valid_type=orm.Dict,
            dynamic=True,
            help='The output parameters of each ``PwBaseWorkChain`` performed``.'
        )
        spec.output(
            'chemical_shifts',
            valid_type=orm.Dict,
            help='All the chemical shift values for each element calculated by the WorkChain.'
        )
        spec.output(
            'binding_energies',
            valid_type=orm.Dict,
            help='All the binding energy values for each element calculated by the WorkChain.'
        )
        spec.output_namespace(
            'chemical_shift_spectra',
            valid_type=orm.XyData,
            dynamic=True,
            help='The fully-resolved spectra for each element based on chemical shift.'
        )
        spec.output_namespace(
            'binding_energy_spectra',
            valid_type=orm.XyData,
            dynamic=True,
            help='The fully-resolved spectra for each element based on binding energy.'
        )
        # yapf: disable

    @classmethod
    def get_protocol_filepath(cls):
        """Return ``pathlib.Path`` to the ``.yaml`` file that defines the protocols."""
        from importlib_resources import files

        from . import protocols  # pylint: disable=relative-beyond-top-level

        # import protocols  # pylint: disable=relative-beyond-top-level
        return files(protocols) / 'xps.yaml'

    @classmethod
    def get_default_treatment(cls) -> str:
        """Return the default core-hole treatment.

        :param cls: the workflow class.
        :return: the default core-hole treatment
        """
        return cls._load_treatment_file()['default_treatment']

    @classmethod
    def get_available_treatments(cls) -> dict:
        """Return the available core-hole treatments.

        :param cls: the workflow class.
        :return: dictionary of available treatments, where each key is a treatment and value
                 is another dictionary that contains at least the key `description` and
                 optionally other keys with supplimentary information.
        """
        data = cls._load_treatment_file()
        return {treatment: {'description': values['description']} for treatment, values in data['treatments'].items()}

    @classmethod
    def get_treatment_inputs(
        cls,
        treatment: Optional[dict] = None,
        overrides: Union[dict, pathlib.Path, None] = None,
    ) -> dict:
        """Return the inputs for the given workflow class and core-hole treatment.

        :param cls: the workflow class.
        :param treatment: optional specific treatment, if not specified, the default will be used
        :param overrides: dictionary of inputs that should override those specified by the treatment. The mapping should
            maintain the exact same nesting structure as the input port namespace of the corresponding workflow class.
        :return: mapping of inputs to be used for the workflow class.
        """
        data = cls._load_treatment_file()
        treatment = treatment or data['default_treatment']

        try:
            treatment_inputs = data['treatments'][treatment]
        except KeyError as exception:
            raise ValueError(
                f'`{treatment}` is not a valid treatment. '
                'Call ``get_available_treatments`` to show available treatments.'
            ) from exception
        inputs = recursive_merge(data['default_inputs'], treatment_inputs)
        inputs.pop('description')

        if isinstance(overrides, pathlib.Path):
            with overrides.open() as file:
                overrides = yaml.safe_load(file)

        if overrides:
            return recursive_merge(inputs, overrides)

        return inputs

    @classmethod
    def _load_treatment_file(cls) -> dict:
        """Return the contents of the core-hole treatment file."""
        with cls.get_treatment_filepath().open() as file:
            return yaml.safe_load(file)

    @classmethod
    def get_treatment_filepath(cls):
        """Return ``pathlib.Path`` to the ``.yaml`` file that defines the core-hole treatments for the SCF step."""
        from importlib_resources import files

        from . import protocols

        # import protocols
        return files(protocols) / 'core_hole_treatments.yaml'

    @classmethod
    def get_builder_from_protocol(  # noqa
        cls,
        code,
        structure,
        core_hole_pseudos,
        core_hole_treatments=None,
        protocol=None,
        overrides=None,
        core_levels=None,
        atom_indices=None,
        options=None,
        structure_preparation_settings=None,
        correction_energies=None,
        **kwargs,
    ):  # pylint: disable=too-many-statements
        """Return a builder prepopulated with inputs selected according to the chosen protocol.

        :param code: the ``Code`` instance configured for the ``quantumespresso.pw`` plugin.
        :param structure: the ``StructureData`` instance to use.
        :param core_hole_pseudos: the core-hole pseudopotential (ground-state and
                        excited-state) for the elements to be calculated. These must
                        use the mapping of {"element" : {"1s" : <upf>, "gipaw" : <upf>}}
        :param protocol: the protocol to use. If not specified, the default will be used.
        :core_hole_treatments: optional dictionary to set core-hole treatment for each element,
                        e.g., {"C": "full"}.
        :param overrides: optional dictionary of inputs to override the defaults of the
                          XpsWorkChain itself.
        :param core_levels: the elements and their core-levels to be considered for analysis.
                            e.g., {"C": ["1s"], "Al": ["2s", "2p"]}.
        :param atom_indices: the indices of atoms to be considered for analysis.
        :correction_energies: optional dictionary to set the correction energy to each core level,
                        e.g., {'C': {'1s': 339.79}}.
        :param kwargs: additional keyword arguments that will be passed to the
            ``get_builder_from_protocol`` of all the sub processes that are called by this
            workchain.
        :return: a process builder instance with all inputs defined ready for launch.
        """
        inputs = cls.get_protocol_inputs(protocol, overrides)
        pw_args = (code, structure, protocol)
        # xspectra_args = (pw_code, xs_code, structure, protocol, upf2plotcore_code)

        relax = PwRelaxWorkChain.get_builder_from_protocol(
            *pw_args, overrides=inputs.get('relax', None), options=options, **kwargs
        )
        ch_scf = PwBaseWorkChain.get_builder_from_protocol(
            *pw_args, overrides=inputs.get('ch_scf', None), options=options, **kwargs
        )

        relax.pop('clean_workdir', None)
        relax.pop('structure', None)
        relax.pop('base_final_scf', None)
        ch_scf.pop('clean_workdir', None)
        ch_scf.pop('structure', None)

        abs_atom_marker = orm.Str(inputs['abs_atom_marker'])
        # pylint: disable=no-member
        builder = cls.get_builder()
        builder.relax = relax
        builder.ch_scf = ch_scf
        builder.structure = structure
        builder.abs_atom_marker = abs_atom_marker
        if correction_energies:
            builder.correction_energies = orm.Dict(correction_energies)
            builder.calc_binding_energy = orm.Bool(True)
        else:
            builder.calc_binding_energy = orm.Bool(False)
        builder.clean_workdir = orm.Bool(inputs['clean_workdir'])
        if core_levels is None:
            core_levels = {}
            for element, pseudos in core_hole_pseudos.items():
                if element in structure.get_symbols_set():
                    core_levels[element] = [key for key in pseudos.keys() if key != 'gipaw']
        builder.core_levels = orm.Dict(core_levels)
        if atom_indices:
            builder.atom_indices = orm.List(atom_indices)
        builder.core_hole_pseudos = core_hole_pseudos
        if core_hole_treatments:
            builder.core_hole_treatments = orm.Dict(dict=core_hole_treatments)
        # for get_xspectra_structures
        if structure_preparation_settings:
            builder.structure_preparation_settings = structure_preparation_settings
            if structure_preparation_settings.get('is_molecule_input').value:
                builder.ch_scf.pw.parameters.base.attributes.all['SYSTEM']['assume_isolated'] = 'mt'
                builder.ch_scf.pw.settings = orm.Dict(dict={'gamma_only': True})
                # To ensure compatibility with the gamma_only setting, the k-points must be configured to [1, 1, 1].
                kpoints_mesh = DataFactory('core.array.kpoints')()
                kpoints_mesh.set_kpoints_mesh([1, 1, 1])
                builder.ch_scf.kpoints = kpoints_mesh
                builder.relax.base.pw.settings = orm.Dict(dict={'gamma_only': True})
        # pylint: enable=no-member
        return builder

    def setup(self):
        """Init required context variables."""
        self.ctx.current_structure = self.inputs.structure
        self.ctx.atom_indices = self.inputs.atom_indices.get_list() if 'atom_indices' in self.inputs else None
        # pseudos for all elements to be calculated should be replaced by the ground-state pseudos
        self.ctx.pseudos = {key: value for key, value in self.inputs.ch_scf.pw.pseudos.items()}

        if 'core_levels' in self.inputs.core_levels.get_dict():
            self.ctx.core_levels = self.inputs.core_levels.get_dict()
        else:
            core_levels = {}
            for element, pseudos in self.inputs.core_hole_pseudos.items():
                if element in self.inputs.structure.get_symbols_set():
                    core_levels[element] = [key for key in pseudos.keys() if key != 'gipaw']
            self.ctx.core_levels = core_levels
        for kind in self.inputs.structure.kinds:
            if kind.symbol in self.ctx.core_levels:
                self.ctx.pseudos[kind.name] = self.inputs.core_hole_pseudos[kind.symbol]['gipaw']

    def should_run_relax(self):
        """If the 'relax' input namespace was specified, we relax the input structure."""
        return 'relax' in self.inputs

    def run_relax(self):
        """Run the PwRelaxWorkChain to run a relax PwCalculation."""
        inputs = AttributeDict(self.exposed_inputs(PwRelaxWorkChain, namespace='relax'))
        inputs.metadata.call_link_label = 'relax'
        inputs.structure = self.inputs.structure

        running = self.submit(PwRelaxWorkChain, **inputs)

        self.report(f'launching PwRelaxWorkChain<{running.pk}>')

        return ToContext(relax_workchain=running)

    def inspect_relax(self):
        """Verify that the PwRelaxWorkChain finished successfully."""
        workchain = self.ctx.relax_workchain

        if not workchain.is_finished_ok:
            self.report(f'PwRelaxWorkChain failed with exit status {workchain.exit_status}')
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        relax_params = workchain.outputs.output_parameters
        self.ctx.current_structure = workchain.outputs.output_structure
        self.out('optimized_structure', workchain.outputs.output_structure)
        self.out('output_parameters_relax', relax_params)

    def prepare_structures(self):
        """Get a marked structure for each site.

        Analyses the given structure using ``get_xspectra_structures()`` to obtain both the
        conventional standard form of the crystal structure and the list of symmetrically
        non-equivalent sites. This list is then used to produce a supercell of the
        standardized structure for each selected site with the site marked using a unique
        label.

        If provided, this step will use inputs from ``inputs.structure_preparation_settings``
        and apply them to the CalcFunction call. The accepted inputs (format, default) are:
        - supercell_min_parameter (float, 8.0)
        - standardize_structure (bool, True)
        - is_molecule_input (bool, False)

        Input settings for the spglib analysis within ``get_xspectra_structures`` can be
        provided via ``inputs.spglib_settings`` in the form of a Dict node and must be
        formatted as {<variable_name> : <parameter>} for each variable in the
        ``get_symmetry_dataset()`` method.
        """
        from aiida_qe_xspec.workflows.functions.get_marked_structures import get_marked_structures
        from aiida_qe_xspec.workflows.functions.get_xspectra_structures import get_xspectra_structures

        input_structure = self.ctx.current_structure
        if self.ctx.atom_indices:
            inputs = {
                'atom_indices': self.ctx.atom_indices,
                'marker': self.inputs.abs_atom_marker,
                'metadata': {'call_link_label': 'get_marked_structures'},
            }
            result = get_marked_structures(input_structure, **inputs)
            self.ctx.supercell = input_structure
            self.ctx.equivalent_sites_data = result.pop('output_parameters').get_dict()
        else:
            inputs = {
                'absorbing_elements_list': orm.List(list(self.ctx.core_levels.keys())),
                'absorbing_atom_marker': self.inputs.abs_atom_marker,
                'metadata': {'call_link_label': 'get_xspectra_structures'},
            }  # populate this further once the schema for WorkChain options is figured out
            if 'structure_preparation_settings' in self.inputs:
                optional_cell_prep = self.inputs.structure_preparation_settings
                for key, node in optional_cell_prep.items():
                    inputs[key] = node
            if 'spglib_settings' in self.inputs:
                spglib_settings = self.inputs.spglib_settings
                inputs['spglib_settings'] = spglib_settings
            else:
                spglib_settings = None

            result = get_xspectra_structures(input_structure, **inputs)

            supercell = result.pop('supercell')
            out_params = result.pop('output_parameters')
            if out_params.get_dict().get('structure_is_standardized', None):
                standardized = result.pop('standardized_structure')
                self.out('standardized_structure', standardized)

            # structures_to_process = {Key : Value for Key, Value in result.items()}
            for site in ['output_parameters', 'supercell', 'standardized_structure']:
                result.pop(site, None)
            self.ctx.supercell = supercell
            self.ctx.equivalent_sites_data = out_params['equivalent_sites_data']
            self.out('supercell_structure', supercell)
            self.out('symmetry_analysis_data', out_params)
        structures_to_process = {f'{Key.split("_")[0]}_{Key.split("_")[1]}': Value for Key, Value in result.items()}
        self.report(f'structures_to_process: {structures_to_process}')
        self.ctx.structures_to_process = structures_to_process

    def run_gs_scf(self):
        """Call ``PwBaseWorkChain`` to compute total energy for the supercell."""
        inputs = AttributeDict(self.exposed_inputs(PwBaseWorkChain, namespace='ch_scf'))
        inputs.pw.structure = self.ctx.supercell
        inputs.metadata.call_link_label = 'supercell_xps'

        inputs = prepare_process_inputs(PwBaseWorkChain, inputs)
        inputs.pw.pseudos = {key: value for key, value in self.ctx.pseudos.items()}
        running = self.submit(PwBaseWorkChain, **inputs)

        self.report(f'launched PwBaseWorkChain for supercell<{running.pk}>')

        return running

    def run_all_scf(self):
        """Call all PwBaseWorkChain's required to compute total energies for each absorbing atom site."""
        # scf for supercell
        futures = {}
        if self.inputs.calc_binding_energy:
            gs_future = self.run_gs_scf()
            futures['ground_state'] = gs_future
        # scf for core hole
        structures_to_process = self.ctx.structures_to_process
        equivalent_sites_data = self.ctx.equivalent_sites_data
        abs_atom_marker = self.inputs.abs_atom_marker.value

        ch_treatments = self.inputs.core_hole_treatments.get_dict() if 'core_hole_treatments' in self.inputs else {}
        labels = {}
        for site in structures_to_process:
            abs_element = equivalent_sites_data[site]['symbol']
            labels.setdefault(abs_element, {})
            for orbital in self.ctx.core_levels[abs_element]:
                labels[abs_element].setdefault(orbital, {})
                key = f'{abs_element}_{site}_{orbital}'
                labels[abs_element][orbital][site] = key
                inputs = AttributeDict(self.exposed_inputs(PwBaseWorkChain, namespace='ch_scf'))
                structure = structures_to_process[site]
                inputs.pw.structure = structure
                ch_treatment = ch_treatments.get(abs_element, 'xch_smear')
                inputs.metadata.call_link_label = f'{key}'
                # Get the given settings for the SCF inputs and then overwrite them with the
                # chosen core-hole approximation, then apply the correct pseudopotential pair
                scf_params = inputs.pw.parameters.get_dict()
                ch_treatment_inputs = self.get_treatment_inputs(treatment=ch_treatment)
                new_scf_params = recursive_merge(left=scf_params, right=ch_treatment_inputs)
                if ch_treatment == 'xch_smear':
                    structure_kinds = [kind.name for kind in structure.kinds]
                    structure_kinds.sort()
                    abs_species = structure_kinds.index(abs_atom_marker)
                    new_scf_params['SYSTEM'][f'starting_magnetization({abs_species + 1})'] = 1
                # remove pseudo if the only element is replaced by the marker
                inputs.pw.pseudos = {key: value for key, value in self.ctx.pseudos.items() if key in structure.get_kind_names()}
                inputs.pw.pseudos[abs_atom_marker] = self.inputs.core_hole_pseudos[abs_element][orbital]
                inputs.pw.parameters = orm.Dict(dict=new_scf_params)

                inputs = prepare_process_inputs(PwBaseWorkChain, inputs)

                future = self.submit(PwBaseWorkChain, **inputs)
                futures[key] = future
                self.report(f'launched PwBaseWorkChain for {key}<{future.pk}>')
        self.ctx.labels = labels

        return ToContext(**futures)

    def inspect_all_scf(self):
        """Check that all the PwBaseWorkChain sub-processes finished sucessfully."""
        failed_work_chains = []
        output_params_ch_scf = {}
        for element, element_data in self.ctx.labels.items():
            output_params_ch_scf[element] = {}
            for orbital, orbital_data in element_data.items():
                output_params_ch_scf[element][orbital] = {}
                for site, label in orbital_data.items():
                    work_chain = self.ctx[label]
                    if not work_chain.is_finished_ok:
                        failed_work_chains.append(work_chain)
                        self.report(f'PwBaseWorkChain for ({label}) failed with exit status {work_chain.exit_status}')
                    else:
                        output_params_ch_scf[element][orbital][site] = work_chain.outputs.output_parameters
        if len(failed_work_chains) > 0:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_CH_SCF
        self.ctx.output_params_ch_scf = output_params_ch_scf

    def results(self):
        """Compile all output spectra, organise and post-process all computed spectra, and send to outputs."""

        self.out('output_parameters_ch_scf', self.ctx.output_params_ch_scf)

        kwargs = {'output_params_ch_scf': self.ctx.output_params_ch_scf}
        if self.inputs.calc_binding_energy:
            kwargs['ground_state'] = self.ctx['ground_state'].outputs.output_parameters
            kwargs['correction_energies'] = self.inputs.correction_energies
        kwargs['metadata'] = {'call_link_label': 'compile_final_spectra'}

        voight_gamma = self.inputs.voight_gamma
        voight_sigma = self.inputs.voight_sigma

        equivalent_sites_data = orm.Dict(dict=self.ctx.equivalent_sites_data)
        result = get_spectra_by_element(orm.Dict(self.ctx.core_levels), equivalent_sites_data, voight_gamma, voight_sigma, **kwargs)
        self.out_many(result)

    def on_terminated(self):
        """Clean the working directories of all child calculations if ``clean_workdir=True`` in the inputs."""
        super().on_terminated()

        if self.inputs.clean_workdir.value is False:
            self.report('remote folders will not be cleaned')
            return

        cleaned_calcs = []

        for called_descendant in self.node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                try:
                    called_descendant.outputs.remote_folder._clean()  # pylint: disable=protected-access
                    cleaned_calcs.append(called_descendant.pk)
                except (IOError, OSError, KeyError):
                    pass

        if cleaned_calcs:
            self.report(f"cleaned remote folders of calculations: {' '.join(map(str, cleaned_calcs))}")
