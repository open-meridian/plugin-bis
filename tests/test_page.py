"""The two pages under Manage, and their read tools: what each shows, to
whom, and that a tool answers what its page shows."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from meridian.testing import PageClient

from bis import page as page_module
from bis.page import CONNECTION, DATASETS_PAGE, figures, hold, pages
from bis.sdmx import CBPOL

from conftest import HELD, feed, lake, resolving, want


@pytest.fixture
def client(tmp_path: Path) -> PageClient:
    # The deployment holds `HELD`'s records and no other: the Lake's store
    # mints none, so each other series is reported not held.
    work = feed(tmp_path, resolving(lake()))

    async def run() -> None:
        await work.check()
        await work.on_observations_wanted(want("w-1001", [HELD["WS_CBPOL.D.CA"]], day="2026-10-01"))
        await work.on_observations_wanted(
            want("w-standing", [HELD["WS_CBPOL.D.CA"]], standing=True)
        )

    asyncio.run(run())
    hold(work)
    return PageClient(pages)


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert served == {
        (CONNECTION, "admin"): 200,
        (CONNECTION, "write"): 403,
        (CONNECTION, "read"): 403,
        (DATASETS_PAGE, "admin"): 200,
        (DATASETS_PAGE, "write"): 403,
        (DATASETS_PAGE, "read"): 403,
    }
    # No value on any page: the BIS's figures are the reading roles' to show.
    client.assert_no_account_data("161.125606", "155.98211", "2.25")


def test_connection_says_how_the_bis_is_reached(client: PageClient) -> None:
    text = client.get(CONNECTION, "admin").text
    assert text.index('href="?tab=sources"') < text.index("<h2>Key</h2>")
    assert text.index("<h2>Key</h2>") < text.index("<h2>Limits and use</h2>")
    assert text.index("<h2>Limits and use</h2>") < text.index("<h2>Stream</h2>")
    assert "<h2>Sources</h2>" not in text
    assert "No key needed" in text and "Does not stream" in text
    assert 'href="/.meridian/ui/0.12.0/meridian.css"' in text
    assert "records not held" in text
    sources = client.get(CONNECTION, "admin", tab="sources").text
    assert "<h2>Sources</h2>" in sources and "<h2>Key</h2>" not in sources
    assert sources.count("<tr data-source=") == 2
    assert "Tue 17 Nov 2026" in sources and "Tue 01 Sep 2026" in sources
    assert "The BIS states no time a value is published" in sources


def test_datasets_lists_the_datasets_and_every_series(client: PageClient) -> None:
    text = client.get(DATASETS_PAGE, "admin").text
    assert text.index('href="?tab=records"') < text.index("<h2>Served</h2>")
    assert "bis:bis_cbpol" in text and "bis:bis_long_cpi" in text
    assert "cited as the source" in text and "Not licensed yet" in text
    records = client.get(DATASETS_PAGE, "admin", tab="records").text
    assert "<h2>Records</h2>" in records and "<h2>Served</h2>" not in records
    assert "<om-pager" in records and "Source: BIS" in records
    assert 'data-code="WS_CBPOL.D.CA"' in records and 'data-code="WS_LONG_CPI.M.GB.628"' in records
    assert "actual/365, simple" in records and "not carried" in records
    assert (
        "fixings in bis_cbpol" in records
        and "levels, the BIS&#39;s figures in bis_long_cpi" in records
    )


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    names = {t.name for t in pages.tools}
    assert names == {"read_connection", "read_datasets"}
    connection = client.call_tool("read_connection")
    assert connection.outcome == "unchanged", connection.json
    data = connection.data
    assert data["mode"] == "Sample data" and data["credentials"] == []
    assert data["sessions"] is None
    rates, prices = data["sources"]
    assert rates["dataset"] == "bis:bis_cbpol" and rates["last_release"] == "2026-11-17"
    assert prices["dataset"] == "bis:bis_long_cpi" and prices["last_release"] == "2026-09-01"
    read = client.call_tool("read_datasets").data
    cbpol, cpi = read["served"]
    assert cbpol["dataset"] == "bis:bis_cbpol" and cbpol["arrives"] == "push, pull"
    assert cbpol["recorded"] > 0 and cbpol["licensed"] is False
    assert cpi["dataset"] == "bis:bis_long_cpi"
    held = {r["code"]: r for r in read["records"]}
    assert held["WS_CBPOL.D.CA"]["instrument_id"] == HELD["WS_CBPOL.D.CA"]
    assert held["WS_CBPOL.D.CA"]["source"] == "Bank of Canada"
    assert held["WS_CBPOL.D.CA"]["latest_day"] == "2026-11-16"
    assert held["WS_CBPOL.D.XM"]["miss"] == "not held: reported missing"
    assert held["WS_CBPOL.D.TR"]["miss"] == "not carried"
    assert held["WS_LONG_CPI.M.GB.628"]["convention"] == "An index level, based 2010 = 100"


def test_the_records_are_searched(client: PageClient) -> None:
    text = client.get(DATASETS_PAGE, "admin", q="canada").text
    assert 'type="search"' in text and 'value="canada"' in text
    assert text.count("<tr data-code=") == 1 and "1 of " in text
    nothing = client.get(DATASETS_PAGE, "admin", q="atlantis").text
    assert "No record matches" in nothing


def test_before_the_first_check() -> None:
    page_module._held.clear()
    text = PageClient(pages).get(CONNECTION, "admin").text
    assert "Checking the BIS" in text
    empty = PageClient(pages).get(DATASETS_PAGE, "admin").text
    assert "<h2>Records</h2>" not in empty and 'href="?tab=records"' not in empty


def test_the_bis_not_reached(tmp_path: Path) -> None:
    work = feed(tmp_path)
    work.status.flows[CBPOL].error = "https://stats.bis.org/api/v2: ConnectionRefusedError"
    hold(work)
    text = PageClient(pages).get(CONNECTION, "admin").text
    assert 'state="error"' in text and "Not answering" in text
    assert "ConnectionRefusedError" in text


def test_a_licensed_dataset_is_said_so(client: PageClient) -> None:
    page_module._held["feed"].wants.licensed = frozenset({"bis:bis_cbpol"})
    cbpol, cpi = client.call_tool("read_datasets").data["served"]
    assert cbpol["licensed"] is True and cpi["licensed"] is False


def test_the_figures_are_the_data_roles_in_its_order(client: PageClient) -> None:
    work = page_module._held["feed"]
    said = figures(work.status, work)
    assert [f.label for f in said] == [
        "Connection",
        "Entitled at the vendor",
        "Stream",
        "Last recorded",
    ]
    assert said[2].value == "Does not stream"
