from aiida import orm
from aiida.common import exceptions
from aiida_pseudo.data.pseudo import UpfData
import git
import shutil
import os
from pathlib import Path
import yaml

BASE_URL = 'https://github.com/superstar54/xps-data/raw/main/pseudo_demo/'
base_data_folder = Path.home().joinpath('.aiidalab', 'aiida-qe-xspec', 'data')


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

def download_data():
    print(f'Downloading data...')
    repo_url = 'https://github.com/aiidaplugins/aiida-qe-xspec.git'
    clone_dir = 'temp_repo'

    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)

    git.Repo.clone_from(repo_url, clone_dir)

    src = os.path.join(clone_dir, 'data')
    if os.path.exists(base_data_folder):
        shutil.rmtree(base_data_folder)
    shutil.copytree(src, base_data_folder)
    shutil.rmtree(clone_dir)

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

def get_pseudo_group(group_label):
    """Get the pseudo group with the given label.
    If the group does not exist, create it."""
    groups = (
        orm.QueryBuilder()
        .append(
            orm.Group,
            filters={'label': group_label},
        )
        .all(flat=True)
    )
    if len(groups) == 0:
        group = orm.Group(label=group_label)
        group.store()
    else:
        group = groups[0]
    return group

def import_node_from_file(file_path, group, label=None, filename=None, upf=True):
    """Check if the node already exists in the group.
    if it does, return it.
    if it does not, import it and add it to the group."""
    labels = [node.label for node in group.nodes]
    if label not in labels:
        try:
            node = orm.load_node(file_path)
        except exceptions.NotExistent:
            filename = filename or file_path.name
            if upf:
                node = UpfData(file_path, filename=filename)
            else:
                node = orm.SinglefileData(file_path, filename=filename)
            node.label = label
            node.store()
            group.add_nodes(node)
        return node
    else:
        print(f'Node with label {label} already exists in group {group.label}.')


def install_xps_pseudos():
    xps_folder = base_data_folder.joinpath('xps')
    with open(xps_folder.joinpath('data.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    for group_label, group_data in data.items():
        print(f"Importing pseudopotential group '{group_label}'...")
        corrections = {}
        group = get_pseudo_group(f'xps_{group_label}')
        for element, element_data in group_data.items():
            print(f"Importing pseudopotential for element '{element}'...")
            ground_data = element_data.pop('ground')
            pseudo = ground_data['pseudo']
            file_path = xps_folder.joinpath(group_label, 'ground', pseudo)
            import_node_from_file(file_path, group, label=f'{element}_gs')
            for core_level, core_data in element_data.items():
                pseudo = core_data['pseudo']
                ch_label=f'{element}_{core_level}'
                import_node_from_file(xps_folder.joinpath(group_label, core_level, pseudo), group, ch_label)
                corrections[ch_label] = {'core': core_data['core'], 'exp': core_data['exp']}
        group.base.extras.set('correction', corrections)

def install_xas_pseudos():
    core_wfc_dir = 'core_wfc_data'
    gipaw_dir = 'gipaw_pseudos'
    ch_pseudo_dir = 'ch_pseudos/star1s'
    xas_folder = base_data_folder.joinpath('xas')
    with open(xas_folder.joinpath('data.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    for group_label, group_data in data['pseudos'].items():
        print(f"Importing pseudopotential group '{group_label}'...")
        group = get_pseudo_group(f'xas_{group_label}')
        gipaw_pseudo_dict = group_data['gipaw_pseudos']
        core_wfc_dict = group_data['core_wavefunction_data']
        core_hole_pseudo_dict = group_data['core_hole_pseudos']
        core_wfc_dir = xas_folder.joinpath(group_label, 'core_wfc_data')
        gipaw_dir = xas_folder.joinpath(group_label, 'gipaw_pseudos')
        ch_pseudo_dir = xas_folder.joinpath(group_label, 'ch_pseudos/star1s')
        for element, pseudo in gipaw_pseudo_dict.items():
            print(f"element '{element}'...")
            import_node_from_file(gipaw_dir.joinpath(pseudo), group, label=pseudo)
        for element, data in core_wfc_dict.items():
            print(f"element '{element}'...")
            import_node_from_file(core_wfc_dir.joinpath(data), group, label=data, filename='stdout', upf=False)
        for core_level, data in core_hole_pseudo_dict.items():
            print(f"element '{core_level}'...")
            for element, pseudo in data.items():
                import_node_from_file(ch_pseudo_dir.joinpath(pseudo), group, label=pseudo)
