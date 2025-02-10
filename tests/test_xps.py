from aiida import load_profile, orm
from ase.build import bulk
from aiida.engine import run_get_node
from aiida_qe_xspec.workflows.xps import XpsWorkChain
import numpy as np
from aiida import orm
from aiida_qe_xspec.utils import load_core_hole_pseudos


def test_solid():
    """Test the solid."""
    load_profile()
    atoms = bulk('Si')
    structure = orm.StructureData(ase=atoms)
    code = orm.load_code('qe-7.2-pw@localhost')
    # Load the pseudopotential family.
    kpoints = orm.KpointsData()
    kpoints.set_kpoints_mesh([5, 5, 5])
    #
    options = {
            'resources': {
                'num_machines': 1,
                'num_mpiprocs_per_machine': 2,
            },
        }
    structure_preparation_settings = {
        'supercell_min_parameter': orm.Float(1.0),
        'is_molecule_input': orm.Bool(False),
    }
    # Load the pseudopotential family.
    core_level_list = {'Si': ['2p']}
    core_hole_pseudos, correction_energies = load_core_hole_pseudos(core_level_list, 'pseudo_demo_pbe')
    core_hole_treatments={'Si': 'xch_smear'}
    builder = XpsWorkChain.get_builder_from_protocol(
        structure=structure,
        code=code,
        protocol='fast',
        core_hole_pseudos=core_hole_pseudos,
        core_levels={'Si': ['2p']},
        calc_binding_energy=orm.Bool(True),
        correction_energies=orm.Dict(correction_energies),
        core_hole_treatments=core_hole_treatments,
        structure_preparation_settings=structure_preparation_settings,
        kpoints=kpoints,
        overrides = {'ch_scf': {'pseudo_family': 'SSSP/1.2/PBE/efficiency'}},
        options=options,
    )
    builder.pop('relax')
    _, node = run_get_node(builder)
    np.isclose(node.outputs.binding_energies.get_dict()['Si']['2p']['site_0']['energy'], 99.8438, atol=1e-2)
