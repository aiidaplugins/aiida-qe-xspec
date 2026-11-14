"""Regression tests for inspecting failed XSpectra production workchains."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aiida.common import AttributeDict

from aiida_qe_xspec.workflows.xspectra.core import XspectraCoreWorkChain


@pytest.mark.parametrize('statuses', [(False,), (False, True), (True,)])
def test_inspect_xspectra_production(statuses):
    calculations = []
    for index, success in enumerate(statuses):
        outputs = SimpleNamespace()
        if success:
            outputs.output_parameters = Mock()
            outputs.output_parameters.get_dict.return_value = {'xepsilon': [1.0, 0.0, 0.0]}
        calculations.append(SimpleNamespace(
            pk=index + 1,
            is_finished_ok=success,
            exit_status=0 if success else 300,
            outputs=outputs,
        ))

    workflow = SimpleNamespace(
        ctx=AttributeDict({
            'xspectra_prod_calculations': calculations,
            'finished_lanczos': [],
        }),
        exit_codes=XspectraCoreWorkChain.exit_codes,
        report=Mock(),
    )
    result = XspectraCoreWorkChain.inspect_all_xspectra_prod(workflow)

    expected = None if all(statuses) else workflow.exit_codes.ERROR_SUB_PROCESS_FAILED_XSPECTRA
    assert result == expected
    assert workflow.ctx.finished_lanczos == [node for node in calculations if node.is_finished_ok]
    assert workflow.ctx.get('all_lanczos_computed', False) == all(statuses)
