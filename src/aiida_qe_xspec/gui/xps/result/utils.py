def export_xps_data(outputs):
    """Export the data from the XPS workchain"""
    symmetry_analysis_data = outputs.symmetry_analysis_data.get_dict()
    equivalent_sites_data = symmetry_analysis_data['equivalent_sites_data']
    chemical_shifts = outputs.chemical_shifts.get_dict() if 'chemical_shifts' in outputs else {}
    binding_energies = outputs.binding_energies.get_dict() if 'binding_energies' in outputs else {}

    return (
        chemical_shifts,
        binding_energies,
        equivalent_sites_data,
    )


def xps_spectra_broadening(points, equivalent_sites_data, gamma=0.3, sigma=0.3, _label='', intensity=1.0):
    """Broadening the XPS spectra with Voigt function and return the spectra data"""
    import numpy as np
    from scipy.special import voigt_profile  # pylint: disable=no-name-in-module

    result_spectra = {}
    fwhm_voight = gamma / 2 + np.sqrt(gamma**2 / 4 + sigma**2)
    for element, orbitals in points.items():
        for orbital, data in orbitals.items():
            result_spectra[f'{element}_{orbital}'] = {}
            final_spectra_y_arrays = []
            total_multiplicity = sum(d['multiplicity'] for d in data.values())
            max_core_level_shift = max([d['energy'] for d in data.values()])
            min_core_level_shift = min([d['energy'] for d in data.values()])
            # Energy range for the Broadening function
            x_energy_range = np.linspace(
                min_core_level_shift - fwhm_voight - 1.5,
                max_core_level_shift + fwhm_voight + 1.5,
                500,
            )
            for site, d in data.items():
                # Weight for the spectra of every atom
                relative_core_level_position = d['energy']
                y = (
                    intensity
                    * voigt_profile(x_energy_range - relative_core_level_position, sigma, gamma)
                    *d['multiplicity'] / total_multiplicity
                )
                result_spectra[f'{element}_{orbital}'][site] = [x_energy_range, y]
                final_spectra_y_arrays.append(y)
            total = sum(final_spectra_y_arrays)
            result_spectra[f'{element}_{orbital}']['total'] = [x_energy_range, total]
    return result_spectra
