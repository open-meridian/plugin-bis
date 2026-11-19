"""The BIS's policy rates and long consumer prices into the lake: the current
ranges recorded as the BIS publishes them, and any economy and period
recorded when the lake wants it (W10.4, W10.7), through the SDK's rates
helpers (`meridian.roles.data.rates`, contract v27; ruling 345) and its
`Wants`.

**Push.** At start and every six hours, each dataflow's current range -- a
month of policy rates, thirteen months of consumer prices, every economy in
one request -- is read. An answer whose values read as the last one this
process recorded records nothing; any other is recorded whole, in the lake's
batches, and the lake answers each value it holds unchanged, so nothing is
kept between starts but the answers in storage (decisions/028). A value the
BIS revises within the range is the same row key's next version.

**Rows.** A policy rate is one `Rate` a day, a `fixing` in per cent, its
convention the plugin's statement (series.py), against its economy's
record. A consumer price level is the BIS's figure, one `DerivedSeries`
named `level` a month, marked `published_by` the BIS, its rule the BIS's
series, no inputs, its value an index level based 2010 = 100, valid the
whole month (ruling 136). A value the BIS writes as missing is no row, never
a zero. Each is read from the BIS's text as a `Decimal`, never a float.

**Published time.** The BIS states none: no Last-Modified, and no release
time on a value. So no row states a published time, rather than a wrong
one, and the feed delay is not reported (the suite's
`reports-its-feed-delay`, not presented).

**Subjects.** Each series' record is asked of the deployment by the BIS's
key for it as a `symbol` at `bis` (series.py), through the SDK's
`rates.Feed.subject`, once per process: one the deployment does not hold is
reported missing, once a day, asked again by the SDK, and its rows wait. The
plugin mints nothing. A policy rate whose convention this version does not
hold is read and not recorded, and not asked for.

**Wants.** A want of `bis_cbpol` or `bis_long_cpi` for records the plugin
holds -- a business date, a range of at most a year, or the latest -- is read
from the API for each economy asked and recorded against the want; a period
before the dataset's history is declined `beyond_history`, one the BIS
states nothing for, or one not come yet, `source_silent`; any other subject,
or another kind of data, `not_covered`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import meridian
from meridian.operations import DerivedSeries, MeasureRef, ObservationMeta, SubjectRef
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data
from meridian.roles.data import rates

from .declared import BIS_CBPOL, BIS_LONG_CPI, DERIVED, KEYS, RATE
from .portal import Fetched, Portal, PortalUnreachable, path_for, utc_now
from .raw import RawStore
from .sdmx import CBPOL, CPI_BASE, LONG_CPI, NotSdmx, Observation, Observations, parse
from .series import PUBLISHER, SOURCE, Series

log = logging.getLogger("bis")

#: Each dataflow's dataset, and back.
DATASETS = {CBPOL: BIS_CBPOL, LONG_CPI: BIS_LONG_CPI}
FLOWS = {key: flow for flow, key in DATASETS.items()}
#: The first day each dataflow's history holds: the policy rates from 1946.
HISTORY_FROM = {CBPOL: date(1946, 1, 1), LONG_CPI: date(1200, 1, 1)}
#: The most days one want is answered for: a year.
MOST_DAYS = 366
#: The lake's batch of derived values.
BATCH = 500
#: The BIS's definition's version: it states none.
DEFINITION_VERSION = 1


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000) * 1000


def day_ns(day: date) -> int:
    return _ns(datetime(day.year, day.month, day.day, tzinfo=UTC))


def next_month(day: date) -> date:
    return date(day.year + day.month // 12, day.month % 12 + 1, 1)


@dataclass(frozen=True)
class Outcome:
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0
    unresolved: tuple[str, ...] = ()


@dataclass
class Record:
    """One series as the plugin last saw it: the deployment's record for it,
    or why there is none, and the latest period recorded."""

    series: Series
    instrument_id: str = ""
    miss: str = ""
    latest_day: date | None = None


@dataclass
class FlowStatus:
    """What the plugin last did with one dataflow, for its pages; held in
    memory, lost on a restart and read again by the first check."""

    flow: str
    checked_at: datetime | None = None
    read_at: datetime | None = None
    error: str = ""
    first_day: date | None = None
    latest_day: date | None = None
    fetches: int = 0
    #: Lines that named a value holding none that reads, each with how often seen.
    unread: dict[str, int] = field(default_factory=dict)


@dataclass
class Status:
    """What the plugin last did, for its pages."""

    mode: str = "live"
    started_at: datetime | None = None
    flows: dict[str, FlowStatus] = field(
        default_factory=lambda: {f: FlowStatus(f) for f in (CBPOL, LONG_CPI)}
    )
    #: Each series read, by its key (series.py).
    records: dict[str, Record] = field(default_factory=dict)

    @property
    def checked_at(self) -> datetime | None:
        stamps = [f.checked_at for f in self.flows.values() if f.checked_at]
        return max(stamps) if stamps else None

    @property
    def error(self) -> str:
        return next((f.error for f in self.flows.values() if f.error), "")

    @property
    def fetches(self) -> int:
        return sum(f.fetches for f in self.flows.values())

    @property
    def read(self) -> bool:
        return any(f.read_at for f in self.flows.values())


class Feed(data.Role):
    """The plugin's data role class (open-meridian 0.35: each role one
    class), its acts made on itself -- registered with `meridian.run`, or
    bound to the suite's recorder in its tests -- reading the API, resolving,
    recording, answering wants."""

    def __init__(
        self,
        portal: Portal,
        raw: RawStore,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.portal = portal
        self.raw = raw
        self.now = now
        # One Wants for the plugin's two datasets: their licences read
        # together, each want heard here.
        self.wants = data.Wants(self, KEYS, clock_ns=lambda: _ns(self.now()))
        self.rates = rates.Feed(
            self, SOURCE, wants=self.wants, day_zone="UTC", clock_ns=lambda: _ns(self.now())
        )
        self.status = Status(mode=portal.mode, started_at=now())
        self._recorded: dict[str, str] = {}

    def today(self) -> date:
        return self.now().astimezone(UTC).date()

    def use(self, portal: Portal) -> None:
        """Read from `portal` from now on: sample data turned on or off."""
        if portal.mode != self.portal.mode:
            self.portal = portal
            self.status.mode = portal.mode
            self._recorded.clear()

    # ── Reading the API ─────────────────────────────────────────────────

    async def read(
        self, flow: str, start: date, end: date, area: str = ""
    ) -> tuple[Observations, Fetched, str]:
        """`flow`'s values from `start` to `end`, of `area` or every economy,
        the answer and its key in storage (empty for an answer of no value).
        PortalUnreachable or NotSdmx otherwise."""
        held = self.status.flows[flow]
        fetched = await self.portal.get(path_for(flow, start, end, area))
        held.fetches += 1
        if fetched.empty:
            return Observations(flow), fetched, ""
        key = self.raw.keep(fetched)
        if fetched.status != 200:
            raise PortalUnreachable(f"{fetched.url} answered {fetched.status}")
        read = parse(fetched.text, flow)
        for line in read.unread:
            held.unread[line] = held.unread.get(line, 0) + 1
        for area_read, described in read.described.items():
            self.series(flow, area_read, described.title, described.source)
        return read, fetched, key

    # ── Resolving ───────────────────────────────────────────────────────

    def series(self, flow: str, area: str, title: str = "", source: str = "") -> Record:
        """The record of `flow`'s series for `area`, noted on first sight."""
        made = Series(flow, area, title.strip(), source)
        held = self.status.records.get(made.key)
        if held is None:
            held = self.status.records[made.key] = Record(made)
        elif title and not held.series.name:
            held.series = made
        return held

    async def resolve(self, record: Record) -> str:
        """A series' record in the deployment, by the BIS's key at `bis`;
        empty for one not carried, or one the deployment does not hold,
        reported missing."""
        series = record.series
        if not series.carried:
            return ""
        if record.instrument_id:
            return record.instrument_id
        found = await self.rates.subject(
            series.identifier,
            description=series.description,
            instrument_type=series.instrument_type,
        )
        record.instrument_id = found
        record.miss = "" if found else "not held: reported missing"
        return found

    # ── Recording ───────────────────────────────────────────────────────

    def _rate(self, held: Series, subject: str, seen: Observation, raw_key: str) -> Any:
        assert held.convention is not None
        return self.rates.rate(
            subject,
            BIS_CBPOL,
            "fixing",
            rates.percent(seen.text),
            business_date=seen.day,
            convention=held.convention,
            series=held.key,
            raw_key=raw_key,
        )

    def level_key(self, held: Series, subject: str, day: date) -> str:
        """A level's row key: its series and month, about its record, never a
        published time -- a revision is its next version."""
        return f"{held.key}:level:{day.isoformat()[:7]}@{subject}"

    def level(self, held: Series, subject: str, seen: Observation, raw_key: str) -> DerivedSeries:
        """A month's consumer price level as the BIS's figure (ruling 136):
        marked whose, the BIS's series its rule, no inputs, valid the month."""
        return DerivedSeries(
            meta=ObservationMeta(
                row_key=self.level_key(held, subject, seen.day),
                subjects=[SubjectRef(entity_id=subject)],
                source=ops.Source(dataset=self.wants.dataset(BIS_LONG_CPI)),
                valid_from_ns=day_ns(seen.day),
                valid_until_ns=day_ns(next_month(seen.day)),
                business_date=seen.day.isoformat(),
                raw=self.plugin.raw_record(raw_key[:256]) if raw_key else None,
            ),
            series="level",
            value=rates.index_level(seen.text, CPI_BASE),
            rule=MeasureRef(definition=held.key, version=DEFINITION_VERSION),
            published_by=PUBLISHER,
        )

    async def record(
        self,
        read: Observations,
        key: str,
        *,
        want_id: str = "",
        days: Iterable[date] | None = None,
        subjects: set[str] | None = None,
    ) -> tuple[Outcome, set[str]]:
        """Record `read` -- on `days` and for `subjects` where given -- in the
        lake's batches, against `want_id` where given. What the lake answered,
        and the subjects a row was sent for."""
        flow = read.flow
        dataset = DATASETS[flow]
        wanted = set(days) if days is not None else None
        rows: list[Any] = []
        sent: set[str] = set()
        unresolved: dict[str, None] = {}
        for seen in read.observations:
            if wanted is not None and seen.day not in wanted:
                continue
            record = self.series(flow, seen.area)
            if not record.series.carried:
                continue
            subject = await self.resolve(record)
            if not subject:
                unresolved[record.series.key] = None
                continue
            if subjects is not None and subject not in subjects:
                continue
            first, _ = self.raw.noted(
                f"{record.series.key}:{seen.period}={seen.text}", seen.day, key
            )
            maker = self._rate if flow == CBPOL else self.level
            rows.append(maker(record.series, subject, seen, first.key))
            sent.add(subject)
            if record.latest_day is None or seen.day > record.latest_day:
                record.latest_day = seen.day
        self.raw.save_firsts()
        counts = self.wants.sent_to(dataset)
        before = (counts.recorded, counts.restated, counts.unchanged)
        if flow == CBPOL:
            await self.rates.record(dataset, rows, want_id)
        else:
            await self.record_levels(rows)
        outcome = Outcome(
            counts.recorded - before[0],
            counts.restated - before[1],
            counts.unchanged - before[2],
            tuple(unresolved),
        )
        return outcome, sent

    async def record_levels(self, rows: Sequence[DerivedSeries]) -> None:
        """Send levels in the lake's batches, each answer counted to
        `bis_long_cpi`. A derived value answers no want by its ID: the lake
        holds it under the dataset, where the reader that wanted it reads it."""
        for start in range(0, len(rows), BATCH):
            done = await self.record_derived_series(values=list(rows[start : start + BATCH]))
            self.wants.count(done, BIS_LONG_CPI)

    async def check(self) -> dict[str, Outcome]:
        """Read each dataflow's current range; record it where this process
        has not recorded it as it reads now. What each recording came to."""
        done: dict[str, Outcome] = {}
        for flow in (CBPOL, LONG_CPI):
            held = self.status.flows[flow]
            held.checked_at = self.now()
            start, end = self.portal.current(self.today(), flow)
            try:
                read, _, key = await self.read(flow, start, end)
            except (PortalUnreachable, NotSdmx) as failed:
                held.error = str(failed)
                log.warning("%s was not read: %s", flow, failed)
                continue
            held.error = ""
            held.read_at = self.now()
            if read.observations:
                days = [o.day for o in read.observations]
                held.first_day, held.latest_day = min(days), max(days)
            digest = digest_of(read)
            if digest == self._recorded.get(flow):
                continue
            outcome, _ = await self.record(read, key)
            done[flow] = outcome
            if not outcome.unresolved:
                self._recorded[flow] = digest
            log.info(
                "%s of %s to %s: %d recorded, %d restated, %d unchanged%s",
                flow,
                held.first_day,
                held.latest_day,
                outcome.recorded,
                outcome.restated,
                outcome.unchanged,
                f"; {len(outcome.unresolved)} records not held" if outcome.unresolved else "",
            )
        return done

    # ── Wants ───────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        """Record what the lake wants of the plugin's datasets, or decline it
        (the SDK's `Wants.hear`, answered by `answer`)."""
        await self.wants.hear(heard, self.answer)

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        """A standing want withdrawn: no longer kept current."""
        self.wants.withdraw(heard.message.want_id)
        log.info("standing want %s withdrawn", heard.message.want_id)

    def _days(self, flow: str, want: ops.ObservationsWantedEvent) -> list[date]:
        if want.business_date:
            asked = [date.fromisoformat(want.business_date)]
        elif want.valid_from_ns or want.valid_until_ns:
            start = datetime.fromtimestamp(want.valid_from_ns / 1e9, UTC).date()
            until = want.valid_until_ns - 1 if want.valid_until_ns else _ns(self.now())
            end = datetime.fromtimestamp(until / 1e9, UTC).date()
            asked = [start + timedelta(days=n) for n in range((end - start).days + 1)]
            asked = asked[-MOST_DAYS:]
        else:
            latest = self.status.flows[flow].latest_day
            asked = [latest] if latest else []
        if flow == LONG_CPI:
            return sorted({d.replace(day=1) for d in asked})
        return asked

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from the API: its values recorded against it,
        and each subject declined, with why."""
        flow = FLOWS.get(key, "")
        serves = {CBPOL: RATE, LONG_CPI: DERIVED}.get(flow)
        if serves is None or want.data_type not in ("", serves):
            return {s: "not_covered" for s in subjects}
        held = {
            r.instrument_id: r
            for r in self.status.records.values()
            if r.instrument_id and r.series.flow == flow
        }
        declined = {s: "not_covered" for s in subjects if s not in held}
        asked = [s for s in subjects if s in held]
        if not asked:
            return declined
        if want.standing:
            self.wants.stand(want, asked, kinds)
        days = self._days(flow, want)
        for subject in asked:
            reason = await self._record_days(flow, want, days, held[subject])
            if reason:
                declined[subject] = reason
        return declined

    async def _record_days(
        self, flow: str, want: ops.ObservationsWantedEvent, days: list[date], record: Record
    ) -> str:
        """Record the days asked of one series against the want; why none
        was, or empty."""
        today = self.today()
        if days and all(d < HISTORY_FROM[flow] for d in days):
            return "beyond_history"
        asked = [d for d in days if HISTORY_FROM[flow] <= d <= today]
        if not asked:
            return "source_silent"
        try:
            read, _, key = await self.read(flow, min(asked), max(asked), record.series.area)
        except (PortalUnreachable, NotSdmx) as failed:
            log.warning("want %s: %s was not read: %s", want.want_id, flow, failed)
            return "source_silent"
        _, sent = await self.record(
            read, key, want_id=want.want_id, days=asked, subjects={record.instrument_id}
        )
        return "" if sent else "source_silent"


def digest_of(read: Observations) -> str:
    """What an answer states, as a short digest: its values, never the
    answer's other bytes."""
    stated = repr([(o.area, o.period, o.text) for o in read.observations]).encode()
    return hashlib.sha256(stated).hexdigest()[:16]
