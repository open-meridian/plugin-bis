"""The plugin's pages, under Manage alone: the data role's common pages
(spec/plugin-pages-follow-their-role), Connection and Datasets, in its
order, each also a read tool for agents on the deployment's MCP under the
role's names (`read_connection`, `read_datasets`). Each record is the
role's (`meridian.roles.data`), extended with the BIS's fields; each
template is the role's, with the BIS's nuance at its blocks only, as
plugin-ecb's are.

A data plugin shows its connectivity, its data subscriptions and how its
entitlements resolve, and no market data (the product owner, 2026-10-03):

- **Connection** (`/`): "Key" -- the mode (Live or Sample data), "No key
  needed", what the BIS serves; "Limits and use" -- the BIS states no
  limit, the requests made, the last check and error; "Stream": it does not
  stream. Then a tab of its own (`?tab=sources`), **Sources**, one line per
  source -- the policy rates and the consumer prices: its state, the latest
  period published, its calls, its last error, and in its detail where it
  reads and how far its history reaches.
- **Datasets** (`/datasets`): "Served", "Wants" and "Subjects", each with
  the two datasets; then a tab of its own (`?tab=records`), **Records**:
  each series the BIS publishes, with its convention and the deployment's
  record for it or why there is none -- one line a row, searched and paged
  by the kit's om-pager to fit one screen.

Neither shows a rate or a level: those are the reading roles' to show.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import data

from . import records
from .declared import BIS_CBPOL_DATASET, BIS_LONG_CPI_DATASET, CATALOGUE
from .feed import DATASETS, Feed, FlowStatus, Status
from .portal import BASE, FLOWS
from .sdmx import CBPOL, LONG_CPI
from .series import convention_said

TITLE = "Bank for International Settlements"
#: The kit these pages are built on: 0.12.0's "Facts" and "Next step".
KIT = "0.12.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)

CONNECTION = "/"
DATASETS_PAGE = "/datasets"

#: The longest search the Datasets tab reads.
MOST_QUERY = 100
#: Connection's tabs, and Datasets', by the name their links carry.
CONNECTION_TABS = {"connection": "Connection", "sources": "Sources"}
TABS = {"served": "Served", "records": "Records"}
#: The attribution the BIS's terms ask for, said on the Datasets page beside
#: each dataset's terms in words.
ATTRIBUTION = (
    "Source: Bank for International Settlements (BIS). Cite the BIS as the source, mark a "
    "translation unofficial, and imply no endorsement by the BIS."
)
SOURCE_NAMES = {
    CBPOL: "BIS central bank policy rates",
    LONG_CPI: "BIS long series on consumer prices",
}
SHORT_NAMES = {CBPOL: "Policy rates", LONG_CPI: "Consumer prices"}
READS = {
    CBPOL: "every economy's daily policy rate, the last month",
    LONG_CPI: "every economy's monthly index level, 2010 = 100, the last thirteen months",
}
HISTORY = {
    CBPOL: "Any past day from 1 January 1946, when the lake wants it",
    LONG_CPI: "Any past month of a series, from its first, when the lake wants it",
}
RECORDED_AS = {CBPOL: "fixings", LONG_CPI: "levels, the BIS's figures"}

_held: dict[str, Any] = {}


def hold(feed: Feed) -> None:
    """The feed the pages read, once the plugin has registered."""
    _held["feed"] = feed


def _status() -> tuple[Status, Feed | None]:
    feed: Feed | None = _held.get("feed")
    return (feed.status if feed is not None else Status(), feed)


def _iso(moment: datetime | None) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds") if moment else ""


def _day(day: date | None) -> str:
    return day.isoformat() if day else ""


def _flow_state(held: FlowStatus, mode: str) -> str:
    if held.error and held.read_at is None:
        return "Not answering"
    if held.error:
        return "Answering"
    if held.read_at is None:
        return "Checking the BIS"
    return "Sample data" if mode == "synthetic" else "Answering"


def _state(status: Status) -> tuple[str, str, str]:
    """The head's status: its state, what it means, and its detail."""
    error = status.error
    if error and not status.read:
        return "error", "Not answering", error
    if error:
        return "warn", "Answering", error
    if not status.read:
        return "busy", "Checking the BIS", ""
    misses = [r for r in status.records.values() if r.miss]
    if misses:
        plural = "record" if len(misses) == 1 else "records"
        codes = ", ".join(sorted(r.series.key for r in misses)[:6])
        return (
            "warn",
            f"{len(misses)} {plural} not held",
            codes + (", …" if len(misses) > 6 else ""),
        )
    if status.mode == "synthetic":
        return "ok", "Sample data", ""
    return "ok", "Answering", ""


def _source(flow: str, status: Status, instance: str) -> records.SourceRead:
    held = status.flows[flow]
    synthetic = status.mode == "synthetic"
    return records.SourceRead(
        source=SOURCE_NAMES[flow],
        dataset=f"{instance}:{DATASETS[flow]}",
        state=_flow_state(held, status.mode),
        last_release=_day(held.latest_day),
        calls=held.fetches,
        last_error=held.error,
        reads=(
            "The answer recorded on 2026-11-19, committed with the plugin"
            if synthetic
            else f"{BASE}{FLOWS[flow]}, {READS[flow]}"
        ),
        history=HISTORY[flow],
    )


def connection_read(status: Status, feed: Feed | None) -> records.ConnectionRead:
    state, said, _ = _state(status)
    kept = feed.raw.keys() if feed is not None else []
    window = ""
    if feed is not None and feed.raw.granted:
        window = "in the storage the deployment grants, as its responses settings say"
    elif feed is not None:
        window = "in a directory of the plugin's own: this deployment grants no storage"
    instance = feed.plugin.identity.instance_id if feed is not None else "bis"
    answered = status.read or status.mode == "synthetic"
    return records.ConnectionRead(
        mode="Sample data" if status.mode == "synthetic" else "Live",
        credentials=[],
        entitled_at_vendor=(
            "Every policy rate and long consumer price series the BIS publishes: no key"
            if answered
            else ""
        ),
        limit=(
            "The BIS states none; the plugin asks one request at a time, at most one every "
            "two seconds, and checks for new values every six hours"
        ),
        calls=status.fetches,
        last_call_at=_iso(status.checked_at),
        last_error=status.error,
        sessions=None,
        state=state,
        said=said,
        source=(
            "The answers recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else f"{BASE}, the WS_CBPOL and WS_LONG_CPI dataflows"
        ),
        checked_at=_iso(status.checked_at),
        sources=[_source(flow, status, instance) for flow in (CBPOL, LONG_CPI)],
        responses_kept=len(kept),
        kept_for=window,
    )


def datasets_read(status: Status, feed: Feed | None) -> records.DatasetsRead:
    instance = feed.plugin.identity.instance_id if feed is not None else "bis"
    answered = status.read or status.mode == "synthetic"
    served = data.served(
        CATALOGUE,
        instance,
        feed.wants if feed is not None else None,
        "Yes: no key needed" if answered else "Not asked yet",
    )
    held = sorted(status.records.values(), key=lambda r: (r.series.flow, r.series.area))
    return records.DatasetsRead(
        served=served,
        wants=list(data.want_rows(feed.wants)) if feed is not None else [],
        reads_instruments=True,
        attribution=ATTRIBUTION,
        records=[
            records.RecordRead(
                code=r.series.key,
                area=r.series.area,
                name=r.series.description,
                source=r.series.central_bank,
                dataset=DATASETS[r.series.flow],
                recorded_as=RECORDED_AS[r.series.flow],
                convention=convention_said(r.series),
                instrument_id=r.instrument_id,
                miss=r.miss if r.series.carried else "not carried",
                latest_day=_day(r.latest_day),
            )
            for r in held
        ],
        unread=[
            f"{line} ({n} reads)"
            for flow in status.flows.values()
            for line, n in sorted(flow.unread.items())
        ],
    )


def figures(status: Status, feed: Feed | None) -> list[meridian.Figure]:
    """The data role's figures, in its order (`meridian.roles.data`); the
    BIS's plugin reports none of its own."""
    state, said, why = _state(status)
    if status.mode == "synthetic" and state == "ok":
        connection: Any = "Sample data"
    elif said == "Not answering":
        connection = meridian.Figure("", said, state="error", why=why[:200])
    else:
        error = status.error
        connection = meridian.Figure(
            "", "Answering", state="warn" if error else None, why=error[:200]
        )
    last = feed.wants.counts.last_ns if feed is not None else 0
    return data.figures(
        connection=connection,
        entitled_at_vendor=f"{len(CATALOGUE)} of {len(CATALOGUE)} datasets",
        stream="Does not stream",
        last_recorded=(datetime.fromtimestamp(last / 10**9, UTC) if last else None),
    )


def _moment(value: str) -> str:
    """An ISO moment as a person reads it, to the minute in UTC."""
    if not value:
        return ""
    if len(value) == 10:
        return value
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _weekday(value: str) -> str:
    return date.fromisoformat(value).strftime("%a %d %b %Y") if value else ""


def matching(query: str, *texts: str) -> bool:
    """Whether every word of a search is in one of `texts`, case aside."""
    words = query.lower().split()
    held = " ".join(texts).lower()
    return all(word in held for word in words)


pages.environment.filters["moment"] = _moment
pages.environment.filters["day"] = _weekday


@pages.page(
    CONNECTION,
    "Connection",
    levels="admin",
    answers=records.ConnectionRead,
    name="read_connection",
    description=(
        "How this plugin reaches the Bank for International Settlements' Data Portal API, "
        "as every data plugin's Connection answers it: the mode (Live or Sample data), no "
        "key needed, what the BIS serves, its limits (none stated) and the requests made, "
        "the last check and why it failed if it did; it does not stream. Then the BIS's "
        "own: each source -- the policy rates and the long consumer prices -- with its "
        "state, the latest period it published, its calls and last error; and how many "
        "answers are kept. No rate."
    ),
)
async def connection(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = connection_read(status, feed)
    tab = request.query.get("tab", "connection")
    return pages.answer(
        "connection.html",
        read,
        detail=_state(status)[2],
        # Named apart from the SDK's own `tab` and `tabs` (0.32.3), which
        # would draw the data role's section row in their place.
        view=tab if tab in CONNECTION_TABS else "connection",
        views=CONNECTION_TABS,
        short=SHORT_NAMES,
        cbpol=BIS_CBPOL_DATASET.key,
    )


@pages.page(
    DATASETS_PAGE,
    "Datasets",
    levels="admin",
    answers=records.DatasetsRead,
    name="read_datasets",
    description=(
        "What this plugin serves the lake, as every data plugin's Datasets answers it: its "
        "two datasets as the catalogue declares them (the BIS's central bank policy rates, "
        "daily, as rates; its long consumer price series, monthly, as the BIS's figures), "
        "whether a deployment admin has licensed each, what it recorded and declined; the "
        "standing wants it keeps current and the wants it answered. Then the BIS's own: the "
        "attribution its terms ask for, and each series the BIS publishes with its "
        "convention and the deployment's record for it or why there is none. No rate."
    ),
)
async def datasets(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = datasets_read(status, feed)
    # A browser draws one tab, its search narrowing the records drawn; a
    # tool answers every tab.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    tab = request.query.get("tab", "served")
    tab = "records" if query else tab if tab in TABS else "served"
    shown = [r for r in read.records if matching(query, r.code, r.name, r.source, r.area)]
    return pages.answer(
        "datasets.html",
        read,
        query=query,
        tab=tab,
        tabs=TABS,
        shown=shown,
        cpi=BIS_LONG_CPI_DATASET.key,
        state=_state(status),
        checked_at=_iso(status.checked_at),
    )
