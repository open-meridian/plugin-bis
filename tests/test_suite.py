"""The data suite (meridian.suites), each case the BIS's series present
mapped to the plugin's own conversion of the BIS's recorded answers, the
whole suite passing.

The policy rates are rates, recorded as `Rate` rows (contract v27); the
long consumer prices are the BIS's figures, each level a `DerivedSeries`
marked `published_by` (ruling 136), so it presents
`records-a-derived-series`. The cases a rates-only plugin never presents --
every case about a price, a trade, a quote or an outcome -- are the SDK's
`RATES_NOT_PRESENTED`, each with why. Beside them this plugin names its
own:

- the rates cases about what the BIS never states -- a fixing's volume and
  percentiles (`a-rate-fixing` asks for both), a curve, a bill's two
  conventions, a rate index -- each with why;
- the calendars' two: its datasets declare no calendar (the BIS states
  none, each economy following its own), and it never computes a
  settlement date;
- `reports-its-feed-delay`: the BIS states no published time for a value;
- `records-a-datasets-liveness`: it polls every six hours and records no
  liveness.

`a-same-day-revision` is presented: a policy rate the BIS revises within the
current range is the same row key's next version. The cases every suite
holds that the SDK answers (a replacement, the template catalogue, an event
group heard) are the SDK's.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data.testing import RATES_NOT_PRESENTED, Instruments
from meridian.suites import ANSWERED_BY_SDK, Recorder, run

from bis.portal import Fetched, SyntheticPortal

from conftest import AT, CBPOL, HELD, feed, holding, want

PRESENTED = ("records-a-derived-series",)

NOT_PRESENTED = {
    **{c: why for c, why in RATES_NOT_PRESENTED.items() if c not in PRESENTED},
    "a-rate-fixing": "the BIS states a policy rate alone: no volume and no percentiles",
    "a-curve-for-a-date": "the BIS's series here are single rates and indices: no curve",
    "a-tenor-not-published": "the BIS's series here are single rates and indices: no curve",
    "two-conventions-one-tenor": "the BIS publishes no bill: one convention a rate",
    "a-curve-point-from-another-source": "the BIS publishes no curve point",
    "an-index-level": (
        "the BIS publishes no rate index; its consumer price levels are its figures, "
        "recorded as derived series"
    ),
    "reads-a-calendar": "its datasets declare no calendar: the BIS states none",
    "asks-for-a-settlement-date": (
        "records each value as published; never computes a settlement date"
    ),
    "reports-its-feed-delay": "the BIS states no published time for a value",
    "records-a-datasets-liveness": (
        "it polls the BIS every six hours and records no liveness: its series change weekly at most"
    ),
}


class Revised(SyntheticPortal):
    """The BIS's API, the current range read twice: as recorded, then with
    Canada's policy rate of 16 November revised."""

    def __init__(self) -> None:
        super().__init__(lambda: AT)
        self.reads = 0

    async def get(self, path: str) -> Fetched:
        got = await super().get(path)
        if "WS_CBPOL" not in path:
            return got
        self.reads += 1
        if self.reads == 1:
            return got
        body = got.text.replace("D,CA,2026-11-16,2.5,", "D,CA,2026-11-16,2.75,")
        assert body != got.text
        return Fetched(path, 200, body.encode(), got.fetched_at, got.date)


def _held(recorder: Recorder, ambiguous: bool = False) -> None:
    if ambiguous:
        recorder.answer(
            "ResolveIdentifier",
            lambda _: ops.ResolveIdentifierResult(
                found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS
            ),
        )
        return
    holding(Instruments().answering(recorder))


def producers(tmp: Path) -> dict[str, Callable[[Recorder], Awaitable[None]]]:
    async def read(recorder: Recorder) -> None:
        _held(recorder)
        await feed(tmp, recorder).check()

    async def two_records(recorder: Recorder) -> None:
        _held(recorder, ambiguous=True)
        await feed(tmp, recorder).check()

    async def revised(recorder: Recorder) -> None:
        _held(recorder)
        work = feed(tmp, recorder, portal=Revised())
        await work.check()
        await work.check()
        canada = HELD["WS_CBPOL.D.CA"]
        batches = [
            sorted(r.meta.row_key for r in b.rates if r.meta.subjects[0].entity_id == canada)
            for b in recorder.on("RecordRates")
        ]
        keys = [held for held in batches if held]
        assert len(keys) == 2 and keys[0] == keys[1]

    async def licences(recorder: Recorder) -> None:
        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=CBPOL)]),
        )
        work = feed(tmp, recorder)
        await work.wants.read_licences()
        assert work.wants.licensed == {CBPOL}

    async def declined(recorder: Recorder) -> None:
        _held(recorder)
        work = feed(tmp, recorder)
        asked = want("w-2", ["INS-NOT-CARRIED"], day="2026-11-16").message
        recorder.answer("ObservationsWanted", lambda _: asked)
        await recorder.hear(work)

    async def withdrawn(recorder: Recorder) -> None:
        _held(recorder)
        work = feed(tmp, recorder)
        recorder.answer(
            "WantWithdrawn",
            lambda _: ops.WantWithdrawnEvent(want_id="w-standing", dataset=CBPOL),
        )
        await recorder.hear(work)

    return {
        "an-asset-that-does-not-resolve": two_records,
        "a-subject-declined": declined,
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
        "a-same-day-revision": revised,
        "records-a-derived-series": read,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED, instance_id="bis")
    assert report.passed, report.failures
    assert sorted(report.not_presented) == sorted(NOT_PRESENTED)
    assert len(report.passed_cases) == 6 + len(ANSWERED_BY_SDK)
    assert "records-a-derived-series" in report.passed_cases
    assert report.answered_by_sdk == list(ANSWERED_BY_SDK)
