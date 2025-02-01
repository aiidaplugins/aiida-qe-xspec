from aiida import load_profile, orm
from ase.build import bulk
from aiida.engine import run_get_node
from aiida_qe_xspec.workflows.xps import XpsWorkChain
import numpy as np
from aiida import orm


def load_core_hole_pseudos(core_level_list, pseudo_group='pseudo_demo_pbe'):
    """Load the core hole pseudos."""
    pseudo_group = orm.QueryBuilder().append(orm.Group, filters={'label': pseudo_group}).one()[0]
    all_correction_energies = pseudo_group.base.extras.get('correction', {})
    pseudos = {}
    elements_list = []
    correction_energies = {}
    for label in core_level_list:
        element = label.split('_')[0]
        pseudos[element] = {
            'core_hole': next(pseudo for pseudo in pseudo_group.nodes if pseudo.label == label),
            'gipaw': next(pseudo for pseudo in pseudo_group.nodes if pseudo.label == f'{element}_gs'),
        }
        correction_energies[element] = all_correction_energies[label]['core'] - all_correction_energies[label]['exp']
        elements_list.append(element)
    return pseudos, correction_energies


def test_solid():
    """Test the solid."""
    load_profile()
    atoms = bulk('Si')
    structure = orm.StructureData(ase=atoms)
    code = orm.load_code('qe-7.2-pw@localhost')
    parameters = {
        'CONTROL': {
            'calculation': 'scf',
        },
        'SYSTEM': {
            'ecutwfc': 30,
            'ecutrho': 200,
            'occupations': 'smearing',
            'smearing': 'gaussian',
        },
    }
    # Load the pseudopotential family.
    kpoints = orm.KpointsData()
    kpoints.set_kpoints_mesh([5, 5, 5])
    #
    metadata = {
        'options': {
            'resources': {
                'num_machines': 1,
                'num_mpiprocs_per_machine': 1,
            },
        }
    }
    structure_preparation_settings = {
        'supercell_min_parameter': orm.Float(1.0),
        'is_molecule_input': orm.Bool(False),
    }
    # Load the pseudopotential family.
    core_level_list = ['Si_2p']
    core_hole_pseudos, correction_energies = load_core_hole_pseudos(core_level_list, 'pseudo_demo_pbe')
    core_hole_treatments={'Si': 'xch_smear'}
    builder = XpsWorkChain.get_builder_from_protocol(
        structure=structure,
        code=code,
        protocol='fast',
        pseudos=core_hole_pseudos,
        elements_list=['Si'],
        calc_binding_energy=orm.Bool(True),
        parameters=orm.Dict(dict=parameters),
        correction_energies=orm.Dict(correction_energies),
        core_hole_treatments=core_hole_treatments,
        structure_preparation_settings=structure_preparation_settings,
        kpoints=kpoints,
        metadata=metadata,
    )
    builder.pop('relax')
    _, node = run_get_node(builder)
    np.isclose(node.outputs.binding_energies.Si_be.get_dict()['site_0'], 99.8438, atol=1e-2)
