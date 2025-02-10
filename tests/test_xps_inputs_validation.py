from aiida_qe_xspec.utils import load_core_hole_pseudos
from aiida_qe_xspec.workflows.xps import XpsWorkChain
from aiida import orm, load_profile
import pytest
from aiida.common import ValidationError
from aiida.engine import run

load_profile()

def test_validate_get_builder_from_protocol(etfa_molecule):
    code = orm.load_code('qe-7.2-pw@localhost')
    core_levels = {'C': ['1s']}
    core_hole_pseudos, correction_energies = load_core_hole_pseudos(core_levels, 'pseudo_demo_pbe')
    with pytest.raises(ValidationError, match="The following elements: {'Fe'} are not present in the structure"):
        builder = XpsWorkChain.get_builder_from_protocol(
            structure=etfa_molecule,
            code=code,
            core_hole_pseudos=core_hole_pseudos,
            core_levels={'Fe': ['1s']},
            correction_energies=orm.Dict(correction_energies),
        )
        run(builder)
    with pytest.raises(ValidationError, match="The following elements: {'O'} are required for analysis but their pseudopotentials are not provided."):
        builder = XpsWorkChain.get_builder_from_protocol(
            structure=etfa_molecule,
            code=code,
            core_hole_pseudos=core_hole_pseudos,
            core_levels={'C': ['1s'], 'O': ['1s']},
            correction_energies=orm.Dict(correction_energies),
        )
        run(builder)
    with pytest.raises(ValidationError, match='All atom indices must be within the range of the number of atoms in the structure.'):
        builder = XpsWorkChain.get_builder_from_protocol(
            structure=etfa_molecule,
            code=code,
            core_hole_pseudos=core_hole_pseudos,
            core_levels={'C': ['1s']},
            atom_indices = [0, 100],
            correction_energies=orm.Dict(correction_energies),
        )
        run(builder)
    with pytest.raises(ValidationError, match="The following elements: {'O'} are required for analysis but their pseudopotentials are not provided."):
        builder = XpsWorkChain.get_builder_from_protocol(
            structure=etfa_molecule,
            code=code,
            core_hole_pseudos=core_hole_pseudos,
            core_levels={'C': ['1s']},
            atom_indices = [8],
            correction_energies=orm.Dict(correction_energies),
        )
        run(builder)
