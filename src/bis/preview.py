"""The pages on sample data, each printed as one HTML file:
for looking at them without a deployment.

    python -m bis.preview connection > preview/connection.html
    python -m bis.preview datasets > preview/datasets.html

The plugin's work runs on the SDK's suite recorder in place of a sidecar --
the Bank of Canada's and the Bank of England's policy rates and the euro
area's consumer prices resolved to records the recorder names, every other
series to none (so the "not held" state shows), every batch recorded --
against the answers committed under responses/, at 14:00 UTC on 19 November
2026: the current ranges read, a want for the Bank of Canada's rate of 1
October answered, and one for a Sunday declined. Each page links the kit
where the dashboard serves it, /.meridian/ui/<version>/: served beside the
kit it is styled (meridian-ui's `make serve`, or `make preview SHOTS=...`,
which checks each in a browser); opened on its own it is the page without
the kit, unstyled, which works too. `connection-sources` and
`datasets-records` are each page's second tab. `connection-first` and
`datasets-first` are the pages before the first check, with no want yet:
the role's "not set up yet" states.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .feed import Feed
from .page import CONNECTION, DATASETS_PAGE, hold, pages
from .portal import SyntheticPortal
from .raw import RawStore

AT = datetime(2026, 11, 19, 14, 0, tzinfo=UTC)
PAGES = {
    "connection": CONNECTION,
    "connection-sources": CONNECTION,
    "datasets": DATASETS_PAGE,
    "datasets-records": DATASETS_PAGE,
    "datasets-search": DATASETS_PAGE,
    "connection-first": CONNECTION,
    "datasets-first": DATASETS_PAGE,
}
#: Each page's tab, where it is not the first.
TABS = {"connection-sources": "sources", "datasets-records": "records"}
#: What the Datasets tab's search is shown with, as `datasets-search`.
SEARCHED = "canada"
#: The records the preview's deployment holds, by the BIS's key.
HELD = {
    "WS_CBPOL.D.CA": "INS-01KBISCBPOLCA00000000000",
    "WS_CBPOL.D.GB": "INS-01KBISCBPOLGB00000000000",
    "WS_LONG_CPI.M.XM.628": "INS-01KBISCPIXM000000000000",
}


def _want(want_id: str, subject: str, day: str) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset="bis:bis_cbpol",
            data_type="meridian.v1.Rate",
            subjects=[ops.SubjectRef(entity_id=subject)],
            business_date=day,
        ),
    )


def _feed() -> Feed:
    recorder = Recorder("bis")

    def resolved(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        held = HELD.get(params.identifiers[0].value, "")
        if not held:
            return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)
        return ops.ResolveIdentifierResult(found=True, instrument_id=held)

    recorder.answer("ResolveIdentifier", resolved)
    return recorder.bind(Feed(SyntheticPortal(lambda: AT), RawStore(), now=lambda: AT))


async def synthetic_feed() -> Feed:
    """The feed as sample data leaves it, on the recorder."""
    feed = _feed()
    await feed.check()
    canada = HELD["WS_CBPOL.D.CA"]
    await feed.on_observations_wanted(_want("want-1001", canada, "2026-10-01"))
    await feed.on_observations_wanted(_want("want-1004", canada, "2026-10-04"))
    return feed


def render(page: str) -> str:
    feed = _feed() if page.endswith("-first") else asyncio.run(synthetic_feed())
    hold(feed)
    query = {"q": SEARCHED} if page == "datasets-search" else {}
    if page in TABS:
        query = {"tab": TABS[page]}
    answer = PageClient(pages).get(PAGES[page], "admin", **query)
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
