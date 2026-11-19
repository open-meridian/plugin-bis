"""What this version declares beside its role, `data` (W8.1, W4.1; the
catalogue from contract v18), built from code and used twice: `__main__`
registers with it, and `meridian plugin upload` reads it from the built image
(pyproject.toml's `[tool.meridian] declaration`).

**The catalogue: two datasets** (the product owner, items 128 and 140,
2026-11-19: Tier 1; their keys proposed, the product owner's to approve),
each pushed as the BIS publishes it and any past period pulled when the lake
wants it:

- **`bis_cbpol`**, central bank policy rates (the `WS_CBPOL` dataflow):
  `vendor` the BIS, no aggregator -- the BIS compiles each central bank's
  rate itself and names the bank on each series; `data_types` rates
  (`meridian.v1.Rate`), each day's a fixing; `modes` `push` and `pull`;
  `cadence` a day; `history` about 29,500 days, from 1 January 1946 (the
  Bank of England's, the earliest); its day UTC's, ending at midnight -- the
  economies' days differ, and the business date is the date the BIS states;
  no calendar: each rate follows its own economy's, which the BIS does not
  state.
- **`bis_long_cpi`**, long series on consumer prices (`WS_LONG_CPI`, the
  index levels based 2010 = 100): the BIS's figures, each month's level a
  `DerivedSeries` marked `published_by` the BIS (ruling 136); `modes` `push`
  and `pull`; `cadence` about a month; `history` 0, "as each series
  states": each economy's series begins in its own month; UTC's day; no
  calendar.

Both: no venue; their terms and pricing (contract 30, ruling 1032) the
BIS's, in plain words (`BIS_TERMS`), and no licence declared -- a
deployment's licence, set on the Data sources page, is the one enforced, and
the plugin says nothing of whether a deployment meets anyone's terms; a gap
asked again (`gap_recovery` `backfill`, W10.14): the API serves every past
period.

**Storage:** the API's answers (raw.py), archivable, ten years by default.
"""

from __future__ import annotations

from meridian import DatasetDeclaration
from meridian.declaration import RecordKind

from .raw import DEFAULT_WINDOW_DAYS, RESPONSES

#: The datasets' keys (proposed): rows name `<instance>:bis_cbpol` and
#: `<instance>:bis_long_cpi`.
BIS_CBPOL = "bis_cbpol"
BIS_LONG_CPI = "bis_long_cpi"
KEYS = (BIS_CBPOL, BIS_LONG_CPI)
VENDOR = "Bank for International Settlements"
RATE = "meridian.v1.Rate"
#: A publisher's figure (contract v28, amended 2026-10-31, ruling 955).
DERIVED = "meridian.v1.DerivedSeries"
#: A day, and about a month, in seconds.
CADENCE = 86_400
MONTHLY = 30 * 86_400
#: The policy rates since 1 January 1946, in days.
CBPOL_HISTORY = 29_500
#: The economies' days differ: a business date is the date the BIS states.
DAY_TIME_ZONE = "UTC"
DAY_END_MINUTE = 0

#: The BIS's terms, in plain words (contract 30, ruling 1032), as
#: docs/terms.md summarises them: its legal page (https://data.bis.org/help/legal),
#: read by the research on 2026-11-18.
BIS_TERMS = (
    "The BIS Data Portal's API: free, no key or account. The BIS allows use of its statistics "
    "provided the BIS is cited as the source, a translation is marked unofficial, and no "
    "endorsement by the BIS is implied; including them in a commercial product must not add "
    "a charge for them to its users, and no other use is permitted. The API is offered as "
    "is, and may be suspended, versioned or limited."
)
CBPOL_TERMS = BIS_TERMS + (
    " Each policy rate is its central bank's, as the BIS compiles it; the BIS names the bank "
    "on each series. This dataset states each rate's convention as its money market's, which "
    "the BIS does not state."
)
CPI_TERMS = BIS_TERMS + (
    " The long consumer price series are the BIS's compilation from national sources, each "
    "level the BIS's figure, based 2010 = 100."
)


def _dataset(
    key: str, data_type: str, cadence: int, history: int, terms: str
) -> DatasetDeclaration:
    return DatasetDeclaration(
        key=key,
        vendor=VENDOR,
        data_types=[data_type],
        modes=["push", "pull"],
        cadence=cadence,
        history=history,
        terms_and_pricing=terms,
        gap_recovery="backfill",
        day_time_zone=DAY_TIME_ZONE,
        day_end_minute=DAY_END_MINUTE,
    )


BIS_CBPOL_DATASET = _dataset(BIS_CBPOL, RATE, CADENCE, CBPOL_HISTORY, CBPOL_TERMS)
BIS_LONG_CPI_DATASET = _dataset(BIS_LONG_CPI, DERIVED, MONTHLY, 0, CPI_TERMS)
CATALOGUE = [BIS_CBPOL_DATASET, BIS_LONG_CPI_DATASET]

RESPONSES_KIND = RecordKind(RESPONSES, "Raw responses", window_days=DEFAULT_WINDOW_DAYS)
