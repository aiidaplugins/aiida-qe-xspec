from aiida import load_profile, orm
import os
import argparse
import importlib

# get absolute path of this file
dir_path = os.path.dirname(os.path.realpath(__file__))

load_profile()

def main():
    parser = argparse.ArgumentParser(description='Create a pseudo group and add pseudos.')
    parser.add_argument('folder_path', help='Path to the data folder.')
    args = parser.parse_args()
    folder_path = args.folder_path
    path = os.path.join(dir_path, folder_path)
    # check if group exists
    builder = orm.QueryBuilder()
    builder.append(orm.Group, filters={'label': folder_path})
    if len(builder.all()) == 0:
        # create group
        group = orm.Group(label=folder_path)
        group.store()
    else:
        group = builder.all()[0][0]
    # loop all files in path, if file ends with .UPF, store it
    for file in os.listdir(path):
        if file.endswith('.UPF'):
            label = file.split('.')[0]
            ch = file.split('.')[1]
            if ch.startswith('star'):
                orbital = ch[4:]
            else:
                orbital = 'gs'
            label = f'{label}_{orbital}'
            labels = [node.label for node in group.nodes]
            if label in labels:
                continue
            pseudo = orm.UpfData(os.path.join(path, file))
            pseudo.label = label
            pseudo.store()
            print(f'{label}: {pseudo.pk}')
            group.add_nodes(pseudo)
    #
    module_to_load = f'{folder_path}.datas'
    datas = importlib.import_module(module_to_load)
    for key, value in datas.datas.items():
        print(key, value)
        group.base.extras.set(key, value)
    os.system(f'rm {folder_path}.aiida')
    os.system(f'verdi archive create {folder_path}.aiida --groups {folder_path}')

if __name__ == '__main__':
    main()
