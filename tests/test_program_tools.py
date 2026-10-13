"""
Spreadsheet-style entry and the browser_program tool, in a real headless Chrome through the real ComexToolService:
a whole block of cells in ONE key call (Tab between cells, Enter between rows), a program that types a table and
reads it back, the helpers ported from browser-harness, and the agent-facing tool end to end.
"""

from __future__ import annotations

import pytest

from services.program_runtime import ProgramRunner, sandbox_status
from tests.browser_lab import find_chrome
from tests.test_program_runtime import Rig, lab  # noqa: F401  (the real-browser fixtures)

pytestmark = [pytest.mark.skipif(find_chrome() is None, reason="no Chrome/Chromium installed"),
              pytest.mark.skipif(not sandbox_status()[0], reason="the program sandbox is not available here")]

TABLE = [[f"3 x {i}", str(3 * i)] for i in range(1, 41)]


@pytest.fixture
async def rig(lab):  # noqa: F811
    r = Rig(lab)
    yield r
    from nervous.cdp_session import _GLOBAL_SESSIONS
    for s in list(_GLOBAL_SESSIONS.values()):
        try:
            await s.stop()
            await s.cdp.close()
        except Exception:
            pass
    _GLOBAL_SESSIONS.clear()


async def _select_first_cell(rig, ctx):
    x, y = await rig.js(ctx, "(() => { const b = document.querySelector('td').getBoundingClientRect(); return [b.x + 5, b.y + 5]; })()")
    res = await rig.service.pointer(ctx, "click", x, y)
    assert res.success, res.error_message


async def test_a_whole_table_goes_in_with_one_key_call(rig):
    await rig.open("sheet.html")
    ctx = rig.ctx()
    await _select_first_cell(rig, ctx)
    text = "\n".join("\t".join(r) for r in TABLE) + "\n"  # the final Enter commits the last cell
    res = await rig.service.press_keys(ctx, keys=[], text=text)
    assert res.success, res.error_message
    assert await rig.js(ctx, "sheetValues(40, 2)") == TABLE


async def test_a_program_types_a_table_and_reads_it_back(rig):
    await rig.open("sheet.html")
    ctx = rig.ctx()
    code = """
x, y = center_of('td')
click_at_xy(x - 40, y)
rows = [["3 x %d" % i, str(3 * i)] for i in range(1, 41)]
type_table(rows)
back = js('sheetValues(40, 2)')
print('match' if back == rows else 'MISMATCH', len(back))
"""
    res = await ProgramRunner(rig.service, ctx).run(code, timeout_s=30)
    assert res.ok and res.stdout.split() == ["match", "40"], res.to_text()
    assert res.rpc_calls <= 6  # the table itself was one browser operation


async def test_ported_helpers_fill_framework_inputs_and_dispatch_keys(rig):
    await rig.open("form.html")
    ctx = rig.ctx()
    code = """
fill_input('#name', 'Pranav')
dispatch_key('#box', 'Enter')
s = js('formState()')
print(s['name'], s['events'] >= 2, s['keys'], js("document.getElementById('go').disabled"))
"""
    res = await ProgramRunner(rig.service, ctx).run(code, timeout_s=30)
    assert res.ok and res.stdout.split() == ["Pranav", "True", "['Enter']", "False"], res.to_text()
