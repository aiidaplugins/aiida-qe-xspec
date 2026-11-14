"""AiiDAlab QE plugin for X-ray photoelectron spectroscopy (XPS)."""

from aiidalab_qe.plugins import QeAppPlugin


class XpsPlugin(QeAppPlugin):
    @property
    def outline(self) -> str:
        return 'X-ray photoelectron spectroscopy (XPS)'

    def structure_examples(self):
        from .structure_examples import structure_examples

        return structure_examples

    def configuration(self):
        from .model import XpsConfigurationSettingsModel
        from .setting import XpsConfigurationSettingsPanel

        return {
            'panel': XpsConfigurationSettingsPanel,
            'model': XpsConfigurationSettingsModel,
        }

    def resources(self):
        from .resources import XpsResourceSettingsModel, XpsResourceSettingsPanel

        return {
            'panel': XpsResourceSettingsPanel,
            'model': XpsResourceSettingsModel,
        }

    def result(self):
        from .result import XpsResultsModel, XpsResultsPanel

        return {
            'panel': XpsResultsPanel,
            'model': XpsResultsModel,
        }

    def workchain(self):
        from .workchain import workchain_and_builder

        return workchain_and_builder

    def guides(self):
        from pathlib import Path

        return {
            'title': 'XPS',
            'path': Path(__file__).resolve().parent / 'guides',
        }
