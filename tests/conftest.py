import pytest
from aiida_qe_xspec.gui.xps import structure_examples
from ase.io import read
from aiida import orm

@pytest.fixture
def etfa_molecule():
    atoms = read(structure_examples['structures'][1][1])
    atoms.center(vacuum=3.0)
    atoms.pbc = True
    structure = orm.StructureData(ase=atoms)
    return structure
