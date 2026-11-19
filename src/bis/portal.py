"""The BIS Data Portal's API, where the central bank policy rates and the
long consumer price series are published, and its stand-in.

Two kinds of request are made, and nothing else, each for a range of
periods, as SDMX-CSV (`Accept: application/vnd.sdmx.data+csv;version=2.0.0`):

- the daily policy rates of every economy, or of one --
  `/data/dataflow/BIS/WS_CBPOL/1.0/D.<area>?startPeriod=<day>&endPeriod=<day>`
  (`D.` for every economy);
- the long consumer price index levels of every economy, or of one --
  `/data/dataflow/BIS/WS_LONG_CPI/1.0/M.<area>.628?startPeriod=<month>&endPeriod=<month>`
  (`628`, the index based 2010 = 100; its year-on-year changes are not
  asked).

A range with no value is answered 404 ("NoResultsFound"), read as no value.

Read from the BIS itself: no key, no account, and its terms are its
website's (docs/terms.md). It states no rate limit (the research found
none); the plugin asks one request at a time, at most one every two
seconds, says who it is in its User-Agent, and checks the current ranges
every six hours: the BIS updates the policy rates about weekly and the
consumer prices about monthly. The API states no Last-Modified, so there is
no `If-Modified-Since`: an answer whose values read the same as the last one
recorded records nothing (feed.py).

`SyntheticPortal` answers from the real responses committed under
responses/ (responses/index.json): every policy rate from 3 August to 19
November 2026 and every long CPI level from January 2025 to November 2026,
recorded on 2026-11-19. A request is answered with the recorded rows in its
range and economy, and each current range ends on its recording's last
period whatever the clock says, so the plugin's tests and its e2e run on it,
offline, the same on any day.
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import io
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib import resources
from typing import Any, Protocol

from .sdmx import CBPOL, LONG_CPI, UNITS, period_day

BASE = "https://stats.bis.org/api/v2"
ACCEPT = "application/vnd.sdmx.data+csv;version=2.0.0"
#: Each dataflow's address, before its key.
FLOWS = {
    CBPOL: "/data/dataflow/BIS/WS_CBPOL/1.0/",
    LONG_CPI: "/data/dataflow/BIS/WS_LONG_CPI/1.0/",
}
USER_AGENT = "meridian-bis (+https://github.com/open-meridian/plugin-bis)"
#: The least time between two requests to the portal, in seconds.
SPACING = 2.0
#: How long one request may take.
TIMEOUT = 60.0
#: The most of an answer read: a quarter of every policy rate is about 1.5 MB.
MOST_BYTES = 32 * 1024 * 1024
#: How far each current range reaches back: a month of policy rates, the
#: BIS's weekly updates and a correction among them; thirteen months of
#: consumer prices, a year's revisions with the latest.
CURRENT_DAYS = 31
CURRENT_MONTHS = 13


def key_of(flow: str, area: str = "") -> str:
    """A dataflow's key for one economy, or every one where `area` is empty."""
    if flow == CBPOL:
        return f"D.{area}"
    return f"M.{area}.{UNITS[LONG_CPI]}"


def period_of(flow: str, day: date) -> str:
    """A day as the dataflow's period: the day itself, or its month."""
    return day.isoformat() if flow == CBPOL else day.isoformat()[:7]


def path_for(flow: str, start: date, end: date, area: str = "") -> str:
    """The address of `flow`'s values from `start` to `end`, of `area` or of
    every economy."""
    return (
        f"{FLOWS[flow]}{key_of(flow, area)}"
        f"?startPeriod={period_of(flow, start)}&endPeriod={period_of(flow, end)}"
    )


def flow_of(path: str) -> str:
    """The dataflow an address asks, or empty."""
    return next((flow for flow, at in FLOWS.items() if path.startswith(at)), "")


def months_back(day: date, months: int) -> date:
    """The first day of the month `months` before `day`'s."""
    count = day.year * 12 + day.month - 1 - months
    return date(count // 12, count % 12 + 1, 1)


class PortalUnreachable(Exception):  # noqa: N818 - what the BIS's portal was
    """The portal could not be asked: no answer, or not in time."""


@dataclass(frozen=True)
class Fetched:
    """One answer of the portal's, as received."""

    path: str
    status: int
    body: bytes
    fetched_at: datetime
    date: str = ""

    @property
    def url(self) -> str:
        return BASE + self.path

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    @property
    def empty(self) -> bool:
        """A range with no value: the BIS's 404, NoResultsFound."""
        return self.status == 404


class Portal(Protocol):
    mode: str

    def current(self, today: date, flow: str) -> tuple[date, date]: ...

    async def get(self, path: str) -> Fetched: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def current_range(flow: str, last: date) -> tuple[date, date]:
    """A dataflow's current range ending on `last`."""
    if flow == CBPOL:
        return last - timedelta(days=CURRENT_DAYS), last
    return months_back(last, CURRENT_MONTHS), last


class LivePortal:
    """The BIS's API itself."""

    mode = "live"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        self._lock = asyncio.Lock()
        self._last = 0.0

    def current(self, today: date, flow: str) -> tuple[date, date]:
        return current_range(flow, today)

    async def get(self, path: str) -> Fetched:
        async with self._lock:
            wait = self._last + SPACING - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await asyncio.to_thread(self._get, path)
            finally:
                self._last = time.monotonic()

    def _get(self, path: str) -> Fetched:
        headers = {"User-Agent": USER_AGENT, "Accept": ACCEPT}
        request = urllib.request.Request(BASE + path, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - the BIS's https address
                body = answer.read(MOST_BYTES + 1)
                status = answer.status
                said = answer.headers
        except urllib.error.HTTPError as refused:
            body = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status, said = refused.code, refused.headers
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise PortalUnreachable(f"{BASE}{path}: {type(reason).__name__}") from failed
        if len(body) > MOST_BYTES:
            raise PortalUnreachable(f"{BASE}{path}: answered more than {MOST_BYTES} bytes")
        return Fetched(path, status, body, self._now(), date=said.get("Date", "") if said else "")


@dataclass(frozen=True)
class Recording:
    """One recorded answer: its columns and rows, read, and its Date and
    last period."""

    header: list[str]
    rows: tuple[tuple[str, ...], ...]
    said: str
    last_day: date

    def column(self, name: str) -> int:
        return self.header.index(name)


def _recording(held: Any, entry: dict[str, Any]) -> Recording:
    text = gzip.decompress(held.joinpath(entry["file"]).read_bytes()).decode("utf-8")
    header, *rows = list(csv.reader(io.StringIO(text)))
    return Recording(
        header,
        tuple(tuple(r) for r in rows if r),
        str(entry["date"]),
        period_day(str(entry["last_period"])),
    )


class SyntheticPortal:
    """The responses committed under responses/: each range answered with
    the recorded rows in it, of the economy asked, under its Date."""

    mode = "synthetic"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("responses")
        index = json.loads(held.joinpath("index.json").read_text(encoding="utf-8"))
        self.recordings = {
            CBPOL: _recording(held, index["cbpol"]),
            LONG_CPI: _recording(held, index["cpi"]),
        }
        self.asked: list[str] = []

    def current(self, today: date, flow: str) -> tuple[date, date]:
        """A dataflow's current range, ending on its recording's last period."""
        return current_range(flow, self.recordings[flow].last_day)

    async def get(self, path: str) -> Fetched:
        self.asked.append(path)
        flow = flow_of(path)
        recording = self.recordings.get(flow)
        if recording is None:
            return Fetched(path, 404, b"NoResultsFound", self._now())
        key, _, asked = path.removeprefix(FLOWS[flow]).partition("?")
        query = dict(part.partition("=")[::2] for part in asked.split("&"))
        area = key.split(".")[1] if "." in key else ""
        try:
            start = period_day(query.get("startPeriod", ""))
            end = period_day(query.get("endPeriod", ""))
        except ValueError:
            return Fetched(path, 400, b"Invalid period", self._now())
        at_area, at_period = recording.column("REF_AREA"), recording.column("TIME_PERIOD")
        kept = [
            row
            for row in recording.rows
            if (not area or row[at_area] == area) and start <= period_day(row[at_period]) <= end
        ]
        if not kept:
            return Fetched(path, 404, b"NoResultsFound", self._now(), recording.said)
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(recording.header)
        writer.writerows(kept)
        return Fetched(path, 200, out.getvalue().encode(), self._now(), recording.said)


def portal(synthetic: bool, now: Callable[[], datetime] = utc_now) -> Portal:
    return SyntheticPortal(now) if synthetic else LivePortal(now)
