"""The BIS's SDMX-CSV, read as the BIS wrote it.

The BIS Data Portal's API answers a data request as SDMX-CSV 2.0 (the
`application/vnd.sdmx.data+csv;version=2.0.0` it is asked for, portal.py):
a header line naming each column, then one line an observation, every
dimension and attribute in its own column. Two dataflows are read:

- **`WS_CBPOL`**, central bank policy rates: `FREQ` `D` (daily, end of
  period), `REF_AREA` the economy (an ISO 3166 code, `XM` the euro area),
  `TIME_PERIOD` the day, `OBS_VALUE` the rate, `UNIT_MEASURE` `368`, "per
  cent per year", `UNIT_MULT` `0`; `TITLE`, `SOURCE_REF` (the central bank)
  and `COMPILATION` (what the rate has been, and since when) describe the
  series.
- **`WS_LONG_CPI`**, long series on consumer prices, asked for its levels
  alone: `FREQ` `M`, `REF_AREA`, `TIME_PERIOD` the month (`2026-09`),
  `OBS_VALUE` the index level, `UNIT_MEASURE` `628`, "Index, 2010 = 100".

`OBS_STATUS` `M` marks a value missing, written `NaN`: no value, so no row,
never a zero (a weekend, a closed day, a month not yet published). A value is
kept as the text the BIS wrote and read as a `Decimal` from it, never a
float; a line stating a value that does not read, in another unit or with
another multiplier, is kept as not read, with why, and never recorded.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

#: The two dataflows, as the BIS names them.
CBPOL = "WS_CBPOL"
LONG_CPI = "WS_LONG_CPI"
#: Each dataflow's unit of measure, as its codelist (CL_BIS_UNIT) names it:
#: per cent per year, and an index based 2010 = 100.
UNITS = {CBPOL: "368", LONG_CPI: "628"}
UNIT_NAMES = {"368": "Per cent per year", "628": "Index, 2010 = 100"}
#: The long CPI's base period, as the BIS states it.
CPI_BASE = "2010=100"
#: What the BIS writes for a missing value.
MISSING = {"", "NaN", "nan"}


class NotSdmx(Exception):  # noqa: N818 - what the answer was not
    """An answer that is not the SDMX-CSV asked for."""


@dataclass(frozen=True)
class Observation:
    """One value as the BIS stated it: its dataflow, economy, period (a day
    or a month, as written), the first day of that period, and the value's
    text."""

    flow: str
    area: str
    period: str
    day: date
    text: str

    @property
    def value(self) -> Decimal:
        return Decimal(self.text)


@dataclass(frozen=True)
class Described:
    """A series as the BIS describes it: its title, the source it names
    (the central bank, for a policy rate) and what the series has been."""

    title: str = ""
    source: str = ""
    compilation: str = ""


@dataclass
class Observations:
    """An answer read: its values in order, each series' description by
    economy, and the lines that named a value holding none that reads."""

    flow: str
    observations: list[Observation] = field(default_factory=list)
    described: dict[str, Described] = field(default_factory=dict)
    unread: list[str] = field(default_factory=list)

    @property
    def periods(self) -> list[str]:
        return sorted({o.period for o in self.observations})

    def latest(self, area: str) -> date | None:
        days = [o.day for o in self.observations if o.area == area]
        return max(days) if days else None


def period_day(period: str) -> date:
    """The first day of a period as the BIS writes it: `2026-11-17` is that
    day, `2026-09` the first of September 2026."""
    if len(period) == 7:
        return date.fromisoformat(period + "-01")
    return date.fromisoformat(period)


def parse(text: str, flow: str) -> Observations:
    """An answer of `flow`'s, read; NotSdmx where it is not SDMX-CSV."""
    read = Observations(flow)
    if not text.strip():
        return read
    rows = csv.DictReader(io.StringIO(text))
    columns = set(rows.fieldnames or ())
    if not {"REF_AREA", "TIME_PERIOD", "OBS_VALUE"} <= columns:
        raise NotSdmx(f"the answer names no REF_AREA, TIME_PERIOD and OBS_VALUE: {text[:80]!r}")
    for row in rows:
        area = (row.get("REF_AREA") or "").strip()
        period = (row.get("TIME_PERIOD") or "").strip()
        stated = (row.get("OBS_VALUE") or "").strip()
        if area and area not in read.described:
            read.described[area] = Described(
                title=(row.get("TITLE") or "").strip(),
                source=(row.get("SOURCE_REF") or "").strip(),
                compilation=(row.get("COMPILATION") or "").strip(),
            )
        if stated in MISSING or (row.get("OBS_STATUS") or "").strip() == "M":
            continue
        line = f"{flow} {area} {period}: {stated[:40]!r}"
        unit = (row.get("UNIT_MEASURE") or "").strip()
        if unit != UNITS[flow]:
            read.unread.append(f"{line}, in unit {unit!r}")
            continue
        if (row.get("UNIT_MULT") or "0").strip() != "0":
            read.unread.append(f"{line}, multiplied by 10^{row.get('UNIT_MULT')}")
            continue
        try:
            day = period_day(period)
            number = Decimal(stated)
        except (ValueError, InvalidOperation):
            read.unread.append(line)
            continue
        if not area or not number.is_finite():
            read.unread.append(line)
            continue
        read.observations.append(Observation(flow, area, period, day, stated))
    read.observations.sort(key=lambda o: (o.area, o.day))
    return read
