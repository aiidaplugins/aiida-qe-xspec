"""Panel for XPS plugin."""

import ipywidgets as ipw
from aiidalab_qe.common.panel import ConfigurationSettingsPanel

from .model import BASE_URL, XpsConfigurationSettingsModel


class XpsConfigurationSettingsPanel(
    ConfigurationSettingsPanel[XpsConfigurationSettingsModel],
):
    def __init__(self, model: XpsConfigurationSettingsModel, **kwargs):
        super().__init__(model, **kwargs)

        self._model.observe(
            self._on_input_structure_change,
            'input_structure',
        )
        self._model.observe(
            self._on_pseudo_group_change,
            'pseudo_group',
        )

    def render(self):
        if self.rendered:
            return

        self.core_hole_treatment = ipw.ToggleButtons()
        ipw.dlink(
            (self._model, 'core_hole_treatment_options'),
            (self.core_hole_treatment, 'options'),
        )
        ipw.link(
            (self._model, 'core_hole_treatment'),
            (self.core_hole_treatment, 'value'),
        )

        self.pseudo_group = ipw.Dropdown(
            description='Group:',
            style={'description_width': 'initial'},
        )
        ipw.dlink(
            (self._model, 'pseudo_group_options'),
            (self.pseudo_group, 'options'),
        )
        ipw.link(
            (self._model, 'pseudo_group'),
            (self.pseudo_group, 'value'),
        )

        self.core_levels_widget = ipw.VBox()

        self.structure_type = ipw.ToggleButtons()
        ipw.dlink(
            (self._model, 'structure_type_options'),
            (self.structure_type, 'options'),
        )
        ipw.link(
            (self._model, 'structure_type'),
            (self.structure_type, 'value'),
        )

        self.supercell_min_parameter = ipw.FloatText(
            description='The minimum cell length (Å):',
            disabled=False,
            style={'description_width': 'initial'},
        )
        ipw.link(
            (self._model, 'supercell_min_parameter'),
            (self.supercell_min_parameter, 'value'),
        )

        self.calc_binding_energy = ipw.Checkbox(
            description='Calculate binding energy: ',
            indent=False,
        )
        ipw.link(
            (self._model, 'calc_binding_energy'),
            (self.calc_binding_energy, 'value'),
        )

        self.children = [
            ipw.HTML('<h4>Structure</h4>'),
            ipw.HTML(
                """
                <div style="line-height: 140%; margin-bottom: 10px">
                    Below you can indicate if the material should be treated as a
                    molecule or a crystal.
                </div>
            """
            ),
            ipw.HBox(
                children=[
                    self.structure_type,
                ]
            ),
            ipw.HTML(
                """
                <div style="margin-top: 15px;">
                    <h4>Core-Hole pseudopotential group</h4>
                </div>
            """
            ),
            ipw.HTML(
                f"""
                <div style="line-height: 140%; margin-bottom: 10px">
                    Please select a pseudopotential group, which provide the
                    ground-state and excited-state pseudopotentials for the element.
                    The pseudopotentials are downloaded from this <a href="{BASE_URL}">
                    repository</a>.
                </div>
            """
            ),
            self.pseudo_group,
            ipw.HTML(
                """
                <div style="margin-top: 15px;">
                    <h4>Select core-level</h4>
                </div>
            """
            ),
            ipw.HTML(
                """
                <div style="line-height: 140%;">
                    The list of core-levels to be considered for analysis.
                </div>
            """
            ),
            ipw.HBox(
                children=[
                    self.core_levels_widget,
                ]
            ),
        ]

        self.rendered = True

        self.refresh(specific='widgets')

    def _on_input_structure_change(self, _):
        self.refresh(specific='structure')

    def _on_pseudo_group_change(self, _):
        self.refresh(specific='pseudos')

    def update(self, specific=''):
        if self.updated:
            return
        self._show_loading()
        if not self._model.loaded_from_process or (specific and specific != 'widgets'):
            self._model.update(specific)
        self._build_core_levels_widget()
        self.updated = True

    def _show_loading(self):
        if self.rendered:
            self.core_levels_widget.children = [self.loading_message]

    def _build_core_levels_widget(self):
        if not self.rendered:
            return

        children = []
        elements = self._model.input_structure.get_symbols_set()
        supported_core_levels = self._model.get_supported_core_levels()

        for element in elements:
            if element in supported_core_levels:
                for orbital in supported_core_levels[element]:
                    checkbox = ipw.Checkbox(
                        description=f'{element}_{orbital}',
                        indent=False,
                        layout=ipw.Layout(max_width='100%'),
                    )

                    def get_checked(levels, kind=element, orb=orbital):
                        return orb in levels.get(kind, [])

                    def set_checked(value, kind=element, orb=orbital):
                        updated_levels = self._model.core_levels.copy()
                        if value:
                            updated_levels.setdefault(kind, []).append(orb)
                        else:
                            updated_levels[kind] = [o for o in updated_levels.get(kind, []) if o != orb]
                            if not updated_levels[kind]:
                                del updated_levels[kind]
                        return updated_levels

                    link = ipw.link(
                        (self._model, 'core_levels'),
                        (checkbox, 'value'),
                        [get_checked, set_checked],
                    )
                    self.links.append(link)
                    children.append(checkbox)
            else:
                checkbox = ipw.Checkbox(
                    description=f'{element}, not supported by the selected pseudo group',
                    indent=False,
                    disabled=True,
                    value=False,
                    style={'description_width': 'initial'},
                    layout=ipw.Layout(max_width='100%'),
                )
                children.append(checkbox)

        self.core_levels_widget.children = children
