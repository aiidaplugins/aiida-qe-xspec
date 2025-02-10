"""CalcFunction to compute the spectrum from ``XpsWorkchain``."""
from aiida import orm
from aiida.engine import calcfunction
import numpy as np

def spectra_broadening(points, sigma=0.1, gamma=0.1):
    """Broadening base on the binding energy.

    :param points: a Dict object containing the binding energy and multiplicity for each site.
    :param sigma: a Float node for the sigma parameter of the voigt profile.
    :param gamma: a Float node for the gamma parameter of the voigt profile.
    """
    from scipy.special import voigt_profile  # pylint: disable=no-name-in-module

    fwhm_voight = gamma / 2 + np.sqrt(gamma**2 / 4 + sigma**2)

    result_spectra = {}
    for element, orbitals in points.items():
        for orbital, data in orbitals.items():
            final_spectra_y_arrays = []
            final_spectra_y_labels = []
            final_spectra_y_units = []
            total_multiplicity = sum(d['multiplicity'] for d in data.values())
            final_spectra = orm.XyData()
            max_core_level_shift = max([d['energy'] for d in data.values()])
            min_core_level_shift = min([d['energy'] for d in data.values()])
            # Energy range for the Broadening function
            x_energy_range = np.linspace(
                min_core_level_shift - fwhm_voight - 1.5, max_core_level_shift + fwhm_voight + 1.5, 500
            )
            for site, d in data.items():
                # Weight for the spectra of every atom
                intensity = d['multiplicity'] / total_multiplicity
                relative_peak_position = d['energy']
                final_spectra_y_labels.append(f'{element}_{site}')
                final_spectra_y_units.append('sigma')
                final_spectra_y_arrays.append(
                    intensity* voigt_profile(x_energy_range - relative_peak_position, sigma, gamma)
                )
            final_spectra_y_labels.append(f'{element}_total')
            final_spectra_y_units.append('sigma')
            final_spectra_y_arrays.append(sum(final_spectra_y_arrays))
            final_spectra_x_label = 'energy'
            final_spectra_x_units = 'eV'
            final_spectra_x_array = x_energy_range
            final_spectra.set_x(final_spectra_x_array, final_spectra_x_label, final_spectra_x_units)
            final_spectra.set_y(final_spectra_y_arrays, final_spectra_y_labels, final_spectra_y_units)
            result_spectra[f'{element}_{orbital}'] = final_spectra
    return result_spectra

@calcfunction
def get_spectra_by_element(core_levels, equivalent_sites_data, voight_gamma, voight_sigma, **kwargs):  # pylint: disable=too-many-statements
    """Generate the XPS spectra for each element.

    Calculate the core level shift and binding energy for each element.
    Generate the final spectra using the Voigt profile.

    :param core_levels: a Dict object defining the elements and their core-levels to consider
            when producing spectra, e.g., {"C": ["1s"], "Al": ["2s", "2p"]}.
    :param equivalent_sites_data: an Dict object containing symmetry data.
    :param voight_gamma: a Float node for the gamma parameter of the voigt profile.
    :param voight_sigma: a Float node for the sigma parameter of the voigt profile.
    :param structure: the StructureData object to be analysed
    :returns: Dict objects for all generated spectra and associated binding energy
            and core level shift.

    """
    from copy import deepcopy

    ground_state_node = kwargs.pop('ground_state', None)
    correction_energies = kwargs.pop('correction_energies', orm.Dict()).get_dict()
    ch_nodes = kwargs.pop('ch_nodes', {})
    group_state_energy = ground_state_node.get_dict()['energy'] if ground_state_node is not None else None
    core_levels = core_levels.get_dict()
    equivalency_data = equivalent_sites_data.get_dict()

    data_dict = {element: {} for element in core_levels.keys()}
    for key, xspectra_out_params in ch_nodes.items():
        element, _, site, orbital = key.split('_')
        data_dict[element].setdefault(orbital, {})
        energy = xspectra_out_params.get_dict()['energy']
        data_dict[element][orbital][f'site_{site}'] = {'energy': energy, 'multiplicity': equivalency_data[f'site_{site}']['multiplicity']}

    result = {}
    chemical_shifts = deepcopy(data_dict)
    binding_energies = deepcopy(data_dict)
    for element, orbitals in chemical_shifts.items():
        for orbital in orbitals:
            lowest_energy = min([data['energy'] for data in data_dict[element][orbital].values()])
            for data in chemical_shifts[element][orbital].values():
                data['energy'] -= lowest_energy
            if group_state_energy is not None:
                for data in binding_energies[element][orbital].values():
                    data['energy'] += -group_state_energy + correction_energies[element][orbital]

    result['chemical_shifts'] = orm.Dict(chemical_shifts)
    spectra = spectra_broadening(chemical_shifts,
                                     sigma=voight_sigma.value,
                                     gamma=voight_gamma.value)
    result['chemical_shift_spectra'] = spectra
    if ground_state_node is not None:
        spectra = spectra_broadening(binding_energies,
                                     sigma=voight_sigma.value,
                                     gamma=voight_gamma.value)
        result['binding_energy_spectra'] = spectra
        result['binding_energies'] = orm.Dict(binding_energies)
    return result
