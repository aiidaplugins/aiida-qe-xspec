from aiida import orm
import subprocess


BASE_URL = 'https://github.com/superstar54/xps-data/raw/main/pseudo_demo/'


def load_core_hole_pseudos(core_levels, pseudo_group='pseudo_demo_pbe'):
    """Load the core hole pseudos for the given core levels and pseudo group."""
    pseudo_group = orm.QueryBuilder().append(orm.Group, filters={'label': pseudo_group}).one()[0]
    all_correction_energies = pseudo_group.base.extras.get('correction', {})
    pseudos = {}
    correction_energies = {}
    for element in core_levels:
        pseudos[element] = {
            'gipaw': next(pseudo for pseudo in pseudo_group.nodes if pseudo.label == f'{element}_gs'),
        }
        correction_energies[element] = {}
        for orbital in core_levels[element]:
            label = f'{element}_{orbital}'
            pseudos[element][orbital] = next(pseudo for pseudo in pseudo_group.nodes if pseudo.label == label)
            correction_energies[element][orbital] = all_correction_energies[label]['core'] - all_correction_energies[label]['exp']
    return pseudos, correction_energies

def pseudo_group_exists(group_label):
    groups = (
        orm.QueryBuilder()
        .append(
            orm.Group,
            filters={'label': group_label},
        )
        .all(flat=True)
    )
    return len(groups) > 0 and len(groups[0].nodes) > 0

def install_xps_pseudos():
    import os
    from pathlib import Path
    from aiida_qe_xspec.gui.xps.model import XpsConfigurationSettingsModel

    config_instance = XpsConfigurationSettingsModel()
    for group_label in config_instance.pseudo_group_options:

        if not pseudo_group_exists(group_label):
            print(f"Downloading pseudopotential group '{group_label}'...")
            url = BASE_URL + group_label + '.aiida'
            env = os.environ.copy()
            env['PATH'] = f"{env['PATH']}:{Path.home().joinpath('.local', 'bin')}"

            def run_(*args, **kwargs):
                return subprocess.run(
                    *args, env=env, capture_output=True, check=True, **kwargs
                )

            run_(['verdi', 'archive', 'import', url, '--no-import-group'])
        else:
            print(f"Pseudopotential group '{group_label}' already exists.")
