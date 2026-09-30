import io
from pathlib import Path

import pytest
from aiida import orm
from aiida_pseudo.data.pseudo import UpfData
from aiida_pseudo.groups.family.sssp import SsspFamily
from ase.io import read


pytest_plugins = ('aiida.tools.pytest_fixtures',)


@pytest.fixture(autouse=True)
def _load_aiida_profile(aiida_profile_clean):
    """Load and clean an isolated AiiDA profile for every test."""
    return aiida_profile_clean


def _make_upf(element, label):
    content = f'<UPF version="2.0.1"><PP_HEADER element="{element}" z_valence="1.0"/></UPF>'
    stream = io.BytesIO(content.encode())
    stream.name = f'{element}.upf'
    pseudo = UpfData(file=stream, filename=stream.name)
    pseudo.label = label
    return pseudo.store()


@pytest.fixture
def pw_code(aiida_code_installed):
    """Return a local dummy PW code suitable for building workflow inputs."""
    return aiida_code_installed(
        label='pw-test',
        default_calc_job_plugin='quantumespresso.pw',
        filepath_executable='/bin/true',
    )


@pytest.fixture
def sssp_family():
    """Install the QE 5 default pseudo family with minimal test pseudos."""
    family = SsspFamily(label='SSSP/1.3/PBEsol/efficiency').store()
    pseudos = [_make_upf(element, f'{element}_sssp') for element in ('C', 'F', 'H', 'O')]
    family.add_nodes(pseudos)
    family.set_cutoffs(
        {
            element: {
                'cutoff_wfc': 30.0,
                'cutoff_rho': 240.0,
            }
            for element in ('C', 'F', 'H', 'O')
        },
        stringency='test',
        unit='Ry',
    )
    return family


@pytest.fixture
def xps_pseudo_group():
    """Install the core-hole pseudos used by the XPS builder tests."""
    group = orm.Group(label='pseudo_demo_pbe').store()
    group.add_nodes(
        [
            _make_upf('C', 'C_gs'),
            _make_upf('C', 'C_1s'),
        ]
    )
    group.base.extras.set(
        'correction',
        {
            'C_1s': {
                'core': 1.0,
                'exp': 0.0,
            },
        },
    )
    return group


@pytest.fixture
def etfa_molecule():
    filepath = Path(__file__).parents[1] / 'src/aiida_qe_xspec/gui/xps/structure_examples/ETFA.xyz'
    atoms = read(filepath)
    atoms.center(vacuum=3.0)
    atoms.pbc = True
    return orm.StructureData(ase=atoms)
