from types import SimpleNamespace

import pytest
import yaml

from aiida_qe_xspec import utils


def test_verify_post_install_reports_missing_downloaded_data(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, 'base_data_folder', tmp_path)

    with pytest.raises(RuntimeError, match='Missing downloaded XPS data'):
        utils.verify_setup()


def test_verify_post_install_accepts_complete_groups(tmp_path, monkeypatch):
    xps_data = {
        'pbe': {
            'C': {
                'ground': {'pseudo': 'c.upf'},
                '1s': {'pseudo': 'c-1s.upf', 'core': 1.0, 'exp': 0.0},
            }
        }
    }
    xas_data = {
        'pseudos': {
            'pbe': {
                'gipaw_pseudos': {'C': 'c-gipaw.upf'},
                'core_wavefunction_data': {'C': 'c.dat'},
                'core_hole_pseudos': {'1s': {'C': 'c-1s.upf'}},
            }
        }
    }
    xps_folder = tmp_path / 'xps'
    xas_folder = tmp_path / 'xas'
    xps_folder.mkdir()
    xas_folder.mkdir()
    (xps_folder / 'data.yaml').write_text(yaml.safe_dump(xps_data), encoding='utf-8')
    (xas_folder / 'data.yaml').write_text(yaml.safe_dump(xas_data), encoding='utf-8')
    monkeypatch.setattr(utils, 'base_data_folder', tmp_path)

    def group(labels, corrections=None):
        return SimpleNamespace(
            nodes=[SimpleNamespace(label=label) for label in labels],
            base=SimpleNamespace(extras=SimpleNamespace(get=lambda _key, default=None: corrections or default)),
        )

    groups = {
        'xps_pbe': group(['C_gs', 'C_1s'], {'C_1s': {'core': 1.0, 'exp': 0.0}}),
        'xas_pbe': group(['c-gipaw.upf', 'c.dat', 'c-1s.upf']),
    }

    class QueryBuilder:
        def append(self, _model, filters):
            self.group_label = filters['label']
            return self

        def all(self, flat=True):
            return [groups[self.group_label]] if self.group_label in groups else []

    monkeypatch.setattr(utils.orm, 'QueryBuilder', QueryBuilder)

    utils.verify_setup()
