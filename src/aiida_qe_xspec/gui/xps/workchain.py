from aiida.orm import Bool, Dict, Float, Group, QueryBuilder
from aiida.plugins import WorkflowFactory
from aiida_quantumespresso.common.types import ElectronicType, SpinType
from aiida_qe_xspec.workflows.xps import XpsWorkChain
from aiida_qe_xspec.utils import load_core_hole_pseudos
from aiidalab_qe.utils import (
    enable_pencil_decomposition,
    set_component_resources,
)

# supercell min parameter for different protocols
supercell_min_parameter_map = {
    'fast': 4.0,
    'balanced': 8.0,
    'stringent': 12.0,
}


def update_resources(builder, codes):
    """Update the resources for the builder."""
    set_component_resources(builder.ch_scf.pw, codes.get('pw'))
    enable_pencil_decomposition(builder.ch_scf.pw)


def get_builder(codes, structure, parameters, **kwargs):
    from copy import deepcopy

    protocol = parameters['workchain']['protocol']
    xps_parameters = parameters.get('xps', {})
    core_levels = xps_parameters.pop('core_levels')
    atom_indices = xps_parameters.pop('atom_indices', None)
    # load pseudo for excited-state and group-state.
    pseudo_group = xps_parameters.pop('pseudo_group')
    core_hole_pseudos, correction_energies = load_core_hole_pseudos(core_levels, pseudo_group)
    # update the correction energies by the band gap correction
    band_gap_correction = xps_parameters.pop('band_gap_correction', 0.0)
    for element, levels in correction_energies.items():
        for level, energy in levels.items():
            correction_energies[element][level] = energy - band_gap_correction
    #
    is_molecule_input = True if xps_parameters.get('structure_type') == 'molecule' else False
    # set core hole treatment based on electronic type
    if parameters['workchain']['electronic_type'] == 'metal':
        core_hole_treatment = 'xch_smear'
    else:
        core_hole_treatment = 'xch_fixed'
    # if molecule input, set core hole treatment to full
    if is_molecule_input:
        core_hole_treatment = 'full'
    core_hole_treatments = {element: core_hole_treatment for element in core_levels}
    structure_preparation_settings = {
        'supercell_min_parameter': Float(supercell_min_parameter_map[protocol]),
        'is_molecule_input': Bool(is_molecule_input),
    }
    pw_code = codes['pw']['code']
    overrides_ch_scf = deepcopy(parameters['advanced'])
    if is_molecule_input:
        overrides_ch_scf['pw']['parameters']['SYSTEM']['assume_isolated'] = 'mt'
    overrides = {
        'relax': {
            'base': deepcopy(parameters['advanced']),
            'base_final_scf': deepcopy(parameters['advanced']),
        },
        'ch_scf': overrides_ch_scf,
    }
    # Ensure that VdW corrections are not applied for the core-hole SCF calculation
    # Required to resolve issue #765 (https://github.com/aiidalab/aiidalab-qe/issues/765)
    overrides['ch_scf']['pw']['parameters']['SYSTEM']['vdw_corr'] = 'none'

    builder = XpsWorkChain.get_builder_from_protocol(
        code=pw_code,
        structure=structure,
        protocol=protocol,
        core_hole_pseudos=core_hole_pseudos,
        core_levels=core_levels,
        atom_indices=atom_indices,
        calc_binding_energy=Bool(True),
        correction_energies=Dict(correction_energies),
        core_hole_treatments=core_hole_treatments,
        structure_preparation_settings=structure_preparation_settings,
        electronic_type=ElectronicType(parameters['workchain']['electronic_type']),
        spin_type=SpinType(parameters['workchain']['spin_type']),
        initial_magnetic_moments=parameters['advanced']['initial_magnetic_moments'],
        overrides=overrides,
        **kwargs,
    )
    builder.pop('relax')
    builder.pop('clean_workdir', None)
    # update resources
    update_resources(builder, codes)
    if is_molecule_input:
        # set a large kpoints_distance value to set the kpoints to 1x1x1
        builder.ch_scf.kpoints_distance = Float(5)
        builder.ch_scf.pw.settings = Dict(dict={'gamma_only': True})
    return builder


def update_inputs(inputs, ctx):
    """Update the inputs using context."""
    inputs.structure = ctx.current_structure


workchain_and_builder = {
    'workchain': XpsWorkChain,
    'exclude': ('structure', 'relax'),
    'get_builder': get_builder,
    'update_inputs': update_inputs,
}
