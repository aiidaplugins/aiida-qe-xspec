from aiida import orm


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
