"""Shared stand-ins: the BIS's recorded answers, a fixed clock, the
deployment holding some of the BIS's series' records, and the lake's wants
as the sidecar delivers them."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.roles.data.testing import Instruments, Lake
from meridian.suites import Recorder

from bis.feed import Feed
from bis.portal import SyntheticPortal
from bis.raw import RawStore

#: After the recording: 14:00 UTC on Thursday 19 November 2026.
AT = datetime(2026, 11, 19, 14, 0, tzinfo=UTC)
INSTANCE = "bis"
CBPOL = f"{INSTANCE}:bis_cbpol"
CPI = f"{INSTANCE}:bis_long_cpi"
RATE = "meridian.v1.Rate"
DERIVED = "meridian.v1.DerivedSeries"
#: The records the tests' deployment holds, by the BIS's key at `bis`.
HELD = {
    "WS_CBPOL.D.CA": "INS-CBPOLCA",
    "WS_CBPOL.D.GB": "INS-CBPOLGB",
    "WS_CBPOL.D.US": "INS-CBPOLUS",
    "WS_CBPOL.D.BR": "INS-CBPOLBR",
    "WS_CBPOL.D.KW": "INS-CBPOLKW",
    "WS_LONG_CPI.M.CA.628": "INS-CPICA",
    "WS_LONG_CPI.M.GB.628": "INS-CPIGB",
}


def holding(store: Instruments, *left_out: str) -> Instruments:
    """The deployment holding `HELD`'s records, but `left_out`."""
    for code, instrument in HELD.items():
        if code not in left_out:
            store.hold(instrument, ops.Identifier(scheme="symbol", value=code, source="bis"))
    return store


def resolving(plugin: Recorder) -> Recorder:
    """`plugin` resolving `HELD`'s records by their key at `bis`, and no
    other: a deployment holding only those, minting nothing."""

    def resolved(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        named = params.identifiers[0]
        found = HELD.get(named.value, "") if named.source == "bis" else ""
        if not found:
            return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)
        return ops.ResolveIdentifierResult(found=True, instrument_id=found)

    plugin.answer("ResolveIdentifier", resolved)
    return plugin


def lake(*left_out: str) -> Lake:
    """The lake as a test stands it in, holding the records, and answering a
    batch of the BIS's figures as it answers rates: a row key new recorded,
    the same value again unchanged, a changed one restated."""
    held = Lake(INSTANCE)
    holding(held.instruments, *left_out)
    versions: dict[str, Decimal] = {}

    def derived(params: ops.RecordDerivedSeriesParams) -> ops.RecordDerivedSeriesResult:
        done = ops.RecordDerivedSeriesResult()
        for value in params.values:
            stated, was = as_decimal(value.value.value), versions.get(value.meta.row_key)
            if was is None:
                done.recorded += 1
            elif was == stated:
                done.unchanged += 1
            else:
                done.restated += 1
            versions[value.meta.row_key] = stated
        return done

    held.answer("RecordDerivedSeries", derived)
    return held


def feed(
    tmp: Path, plugin: Recorder | None = None, *, portal: Any = None, at: datetime = AT
) -> Feed:
    """The plugin's work on the lake and the BIS's recorded answers, at `at`:
    its data role class bound to the lake (open-meridian 0.35)."""
    held = plugin if plugin is not None else lake()
    return held.bind(Feed(portal or SyntheticPortal(lambda: at), RawStore(tmp), now=lambda: at))


def want(
    want_id: str,
    subjects: list[str],
    *,
    day: str = "",
    standing: bool = False,
    dataset: str = CBPOL,
    data_type: str = RATE,
    valid_from_ns: int = 0,
    valid_until_ns: int = 0,
) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=dataset,
            data_type=data_type,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            business_date=day,
            standing=standing,
            valid_from_ns=valid_from_ns,
            valid_until_ns=valid_until_ns,
        ),
    )
