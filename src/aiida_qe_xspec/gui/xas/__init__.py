"""AiiDAlab QE plugin for X-ray absorption spectroscopy (XAS)."""

from aiidalab_qe.plugins import QeAppPlugin


class XasPlugin(QeAppPlugin):
    @property
    def outline(self) -> str:
        return 'X-ray absorption spectroscopy (XAS)'

    def structure_examples(self):
        from .structure_examples import structure_examples

        return structure_examples

    def configuration(self):
        from .model import XasConfigurationSettingsModel
        from .setting import XasConfigurationSettingsPanel

        return {
            'panel': XasConfigurationSettingsPanel,
            'model': XasConfigurationSettingsModel,
        }

    def resources(self):
        from .resources import XasResourceSettingsModel, XasResourceSettingsPanel

        return {
            'panel': XasResourceSettingsPanel,
            'model': XasResourceSettingsModel,
        }

    def result(self):
        from .result import XasResultsModel, XasResultsPanel

        return {
            'panel': XasResultsPanel,
            'model': XasResultsModel,
        }

    def workchain(self):
        from .workchain import workchain_and_builder

        return workchain_and_builder
