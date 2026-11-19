"""The plugin's own conversion of the BIS's recorded answers: each policy
rate a fixing in per cent, exact, with the plugin's convention; each
consumer price level the BIS's figure; a series not carried never asked for;
a record not held reported missing and its values waiting; nothing recorded
twice; and the lake's wants answered or declined, with why."""

from __future__ import annotations

import asyncio
from pathlib import Path

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from bis.feed import Feed
from bis.portal import SyntheticPortal
from bis.raw import RawStore

from conftest import AT, CPI, HELD, INSTANCE, resolving, want


def recorder() -> Recorder:
    """The suite's recorder resolving `HELD`'s records, and no other."""
    return resolving(Recorder(INSTANCE))


def work(tmp: Path, plugin: Recorder) -> Feed:
    return plugin.bind(Feed(SyntheticPortal(lambda: AT), RawStore(tmp), now=lambda: AT))


def rates_of(plugin: Recorder) -> list[ops.Rate]:
    return [r for b in plugin.on("RecordRates") for r in b.rates]


def levels_of(plugin: Recorder) -> list[ops.DerivedSeries]:
    return [v for b in plugin.on("RecordDerivedSeries") for v in b.values]


def test_each_policy_rate_is_a_fixing_as_the_bis_wrote_it(tmp_path: Path) -> None:
    plugin = recorder()
    asyncio.run(work(tmp_path, plugin).check())
    sent = rates_of(plugin)
    canada = [r for r in sent if r.meta.subjects[0].entity_id == HELD["WS_CBPOL.D.CA"]]
    last = max(canada, key=lambda r: r.meta.business_date)
    assert last.meta.business_date == "2026-11-16"
    assert last.kind == ops.RATE_KIND_FIXING
    assert str(as_decimal(last.value.value)) == "2.5"
    assert last.value.unit == ops.VALUE_UNIT_PERCENT
    assert last.convention.day_count == ops.DAY_COUNT_ACT_365_FIXED
    assert last.convention.compounding == ops.COMPOUNDING_SIMPLE
    assert last.meta.source.dataset == "bis:bis_cbpol"
    assert not last.meta.source_times, "the BIS states no published time"
    assert last.meta.raw.key.startswith("responses/")
    assert last.meta.row_key == (
        "WS_CBPOL.D.CA:fixing:-:act_365_fixed:simple:2026-11-16@INS-CBPOLCA"
    )
    dollar = [r for r in sent if r.meta.subjects[0].entity_id == HELD["WS_CBPOL.D.US"]]
    assert dollar and all(r.convention.day_count == ops.DAY_COUNT_ACT_360 for r in dollar)
    selic = [r for r in sent if r.meta.subjects[0].entity_id == HELD["WS_CBPOL.D.BR"]]
    assert selic and selic[0].convention.day_count == ops.DAY_COUNT_BUS_252
    assert selic[0].convention.compounding == ops.COMPOUNDING_COMPOUNDED


def test_a_missing_value_is_no_row(tmp_path: Path) -> None:
    # The BIS writes Canada's 11 November (a holiday) as NaN: no row, never a zero.
    plugin = recorder()
    asyncio.run(work(tmp_path, plugin).check())
    days = {
        r.meta.business_date
        for r in rates_of(plugin)
        if r.meta.subjects[0].entity_id == HELD["WS_CBPOL.D.CA"]
    }
    assert "2026-11-15" not in days, "a Sunday"
    assert all(as_decimal(r.value.value) != 0 for r in rates_of(plugin))


def test_a_rate_not_carried_is_never_asked_for(tmp_path: Path) -> None:
    plugin = recorder()
    feed = work(tmp_path, plugin)
    asyncio.run(feed.check())
    asked = {i.value for p in plugin.on("ResolveIdentifier") for i in p.identifiers}
    assert "WS_CBPOL.D.TR" not in asked and "WS_CBPOL.D.CA" in asked
    turkey = feed.status.records["WS_CBPOL.D.TR"]
    assert not turkey.series.carried and not turkey.instrument_id
    assert HELD["WS_CBPOL.D.TR"] not in {r.meta.subjects[0].entity_id for r in rates_of(plugin)}


def test_a_record_not_held_is_reported_missing_and_waits(tmp_path: Path) -> None:
    plugin = recorder()
    feed = work(tmp_path, plugin)
    asyncio.run(feed.check())
    missed = {
        (i.scheme, i.value, i.source)
        for p in plugin.on("ReportMissingInstrument")
        for i in p.identifiers
    }
    assert ("symbol", "WS_CBPOL.D.XM", "bis") in missed
    assert ("symbol", "WS_LONG_CPI.M.XM.628", "bis") in missed
    euro = feed.status.records["WS_CBPOL.D.XM"]
    assert euro.miss == "not held: reported missing" and euro.series.name.startswith(
        "Central bank policy rates - Euro area"
    )
    subjects = {r.meta.subjects[0].entity_id for r in rates_of(plugin)}
    assert subjects == {
        HELD[k] for k in ("WS_CBPOL.D.CA", "WS_CBPOL.D.GB", "WS_CBPOL.D.US", "WS_CBPOL.D.BR")
    }


def test_each_consumer_price_level_is_the_bis_figure(tmp_path: Path) -> None:
    plugin = recorder()
    asyncio.run(work(tmp_path, plugin).check())
    levels = [
        v for v in levels_of(plugin) if v.meta.subjects[0].entity_id == HELD["WS_LONG_CPI.M.GB.628"]
    ]
    september = next(v for v in levels if v.meta.business_date == "2026-09-01")
    assert str(as_decimal(september.value.value)) == "161.125606"
    assert september.value.unit == ops.VALUE_UNIT_INDEX
    assert september.value.index_base == "2010=100"
    assert september.series == "level"
    assert september.published_by == "Bank for International Settlements"
    assert september.rule.definition == "WS_LONG_CPI.M.GB.628"
    assert september.meta.source.dataset == CPI
    assert september.meta.row_key == "WS_LONG_CPI.M.GB.628:level:2026-09@INS-CPIGB"
    # Valid the whole month, UTC.
    assert september.meta.valid_until_ns - september.meta.valid_from_ns == 30 * 86_400 * 10**9


def test_nothing_is_recorded_twice_in_a_process(tmp_path: Path) -> None:
    # Every record held: a second check reading the same values records nothing.
    plugin = Recorder(INSTANCE)
    plugin.answer(
        "ResolveIdentifier",
        lambda p: ops.ResolveIdentifierResult(
            found=True, instrument_id=f"INS-{p.identifiers[0].value}"
        ),
    )
    feed = work(tmp_path, plugin)
    asyncio.run(feed.check())
    before = (len(plugin.on("RecordRates")), len(plugin.on("RecordDerivedSeries")))
    assert before[0] and before[1]
    asyncio.run(feed.check())
    assert (len(plugin.on("RecordRates")), len(plugin.on("RecordDerivedSeries"))) == before


def test_a_restart_names_the_answer_each_value_was_first_read_from(tmp_path: Path) -> None:
    one, two = recorder(), recorder()
    asyncio.run(work(tmp_path, one).check())
    asyncio.run(work(tmp_path, two).check())
    first = {r.meta.row_key: r.meta.raw.key for r in rates_of(one)}
    again = {r.meta.row_key: r.meta.raw.key for r in rates_of(two)}
    assert first and again == first


def _declined(plugin: Recorder) -> dict[str, str]:
    return {
        s: ops.UnansweredReason.Name(d.reason) for d in plugin.on("DeclineWant") for s in d.subjects
    }


def test_a_past_day_wanted_is_recorded_against_the_want(tmp_path: Path) -> None:
    plugin = recorder()
    feed = work(tmp_path, plugin)
    asyncio.run(feed.check())
    canada = HELD["WS_CBPOL.D.CA"]
    plugin.answer("ObservationsWanted", lambda _: want("w-1", [canada], day="2026-10-01").message)
    asyncio.run(plugin.hear(feed))
    against = [b for b in plugin.on("RecordRates") if b.want_id == "w-1"]
    assert against and [r.meta.business_date for r in against[0].rates] == ["2026-10-01"]
    assert str(as_decimal(against[0].rates[0].value.value)) == "2.25"
    assert any("D.CA?startPeriod=2026-10-01&endPeriod=2026-10-01" in p for p in feed.portal.asked)  # type: ignore[attr-defined]


def test_wants_declined_with_why(tmp_path: Path) -> None:
    plugin = recorder()
    feed = work(tmp_path, plugin)
    asyncio.run(feed.check())
    canada = HELD["WS_CBPOL.D.CA"]
    for n, (subjects, day) in enumerate(
        [([canada], "2026-10-04"), ([canada], "1900-01-02"), (["INS-ELSE"], "2026-10-01")]
    ):
        asked = want(f"w-{n}", subjects, day=day).message
        plugin.answer("ObservationsWanted", lambda _, held=asked: held)  # type: ignore[misc]
        asyncio.run(plugin.hear(feed))
    reasons = [ops.UnansweredReason.Name(d.reason) for d in plugin.on("DeclineWant")]
    assert reasons == [
        "UNANSWERED_REASON_SOURCE_SILENT",
        "UNANSWERED_REASON_BEYOND_HISTORY",
        "UNANSWERED_REASON_NOT_COVERED",
    ]


def test_a_month_of_consumer_prices_wanted(tmp_path: Path) -> None:
    plugin = recorder()
    feed = work(tmp_path, plugin)
    asyncio.run(feed.check())
    before = len(levels_of(plugin))
    canada = HELD["WS_LONG_CPI.M.CA.628"]
    asked = want(
        "w-cpi", [canada], day="2025-03-15", dataset=CPI, data_type="meridian.v1.DerivedSeries"
    )
    plugin.answer("ObservationsWanted", lambda _: asked.message)
    asyncio.run(plugin.hear(feed))
    wanted = levels_of(plugin)[before:]
    assert [v.meta.business_date for v in wanted] == ["2025-03-01"]
    assert not plugin.on("DeclineWant")
