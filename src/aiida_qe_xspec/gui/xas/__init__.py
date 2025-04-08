from importlib import resources as importlib_resources

import yaml

from aiidalab_qe.common.panel import PluginOutline
from aiida_qe_xspec.gui import xas as xas_folder

from .model import XasConfigurationSettingsModel
from .resources import XasResourceSettingsModel, XasResourceSettingsPanel
from .result import XasResultsModel, XasResultsPanel
from .setting import XasConfigurationSettingsPanel
from .structure_examples import structure_examples
from .workchain import workchain_and_builder

class XasPluginOutline(PluginOutline):
    title = 'X-ray absorption spectroscopy (XAS)'


xas = {
    'outline': XasPluginOutline,
    'structure_examples': structure_examples,
    'configuration': {
        'panel': XasConfigurationSettingsPanel,
        'model': XasConfigurationSettingsModel,
    },
    'resources': {
        'panel': XasResourceSettingsPanel,
        'model': XasResourceSettingsModel,
    },
    'result': {
        'panel': XasResultsPanel,
        'model': XasResultsModel,
    },
    'workchain': workchain_and_builder,
}
