"""The BIS series this version carries, what each one is, and the record it
is recorded against: the plugin's series map.

**Central bank policy rates** (`WS_CBPOL`, daily). Each economy's policy
rate is one `interest_rate` referential record, asked of the deployment by
the BIS's key for the series as a `symbol` at the source `bis` --
`WS_CBPOL.D.CA` for the Bank of Canada's -- a name **proposed** with this
version for the platform's seed: the platform seeds none yet, so until a
deployment holds a record its rates wait, reported missing, never minted.
Each day's rate is a `fixing`, in per cent, as the BIS states it ("per cent
per year").

**Each rate's convention.** The lake refuses a rate with no convention
(`Rate.convention`, never unset), and the BIS states none: its unit is
"per cent per year". A policy rate is the rate its central bank sets for its
own money market, so this version states each one simple, on the day count
of that currency's overnight money market as its administrator publishes its
benchmark (actual/360 for the dollar, the euro, the Swiss franc, the Swedish
krona, the renminbi, the rupiah, the Icelandic króna, the dirham, the Philippine
peso, the Serbian dinar; actual/365 for sterling, the Canadian and Australian
dollars, the yen, the Turkish lira; business/252, compounded annually, for
Brazil's Selic) -- the plugin's statement, said on the Datasets page, never the BIS's. An economy whose
money-market day count this version does not hold is **not carried**: its
rates are read and not recorded, and the Datasets page says why, rather than
guess one.

**Long consumer prices** (`WS_LONG_CPI`, monthly, its levels). Each
economy's index is one `index` referential record, asked by
`WS_LONG_CPI.M.<area>.628` at `bis` (proposed, as above); each month's level
is the BIS's figure, a `DerivedSeries` named `level` marked `published_by`
the BIS (ruling 136), its business date the month's first day, valid the
whole month, based 2010 = 100. Every economy the BIS publishes is carried:
an index level needs no convention.
"""

from __future__ import annotations

from dataclasses import dataclass

from meridian.operations import RateConvention

from .sdmx import CBPOL, LONG_CPI, UNITS

#: The source each record's symbol is scoped to (proposed).
SOURCE = "bis"
PUBLISHER = "Bank for International Settlements"
INTEREST_RATE, INDEX = "interest_rate", "index"

ACT_360 = RateConvention(day_count="act_360", compounding="simple")
ACT_365 = RateConvention(day_count="act_365_fixed", compounding="simple")
#: Brazil's Selic: an annual rate on business days over 252, compounded.
BUS_252 = RateConvention(day_count="bus_252", compounding="compounded", periods_per_year=1)

#: Each economy's money-market day count, as its overnight benchmark's
#: administrator publishes it, or as the central bank states it for the
#: facility its policy rate is set on: SOFR, €STR, SARON, SWESTR, DESTR,
#: CZEONIA, HUFONIA, TIIE de fondeo, the Chilean, Colombian and Peruvian
#: interbank overnight rates, ROBOR, JIBOR (Bank Indonesia), MONIA (Bank
#: Al-Maghrib), PHIREF (the Bankers Association of the Philippines'
#: methodology, April 2021: the basis is the benchmark's, not the BSP's), the
#: Central Bank of Iceland's facility rates, the National Bank of Serbia's repo
#: and the People's Bank of China's rule for RMB loan interest (the BIS's
#: Chinese series is the Loan Prime Rate) on 360; SONIA, CORRA, AONIA, NZIONIA,
#: TONA, HONIA, ZARONIA, KOFR, NOWA, WIRON, MYOR, THOR, MIBOR, SHIR, RUONIA
#: and TLREF (Borsa Istanbul's methodology: actual/365, the simple rate, never
#: the compounded one) on 365. Sources: bis-daycount research, 2026-11-19.
#: China: a June 2026 PBoC consultation draft (people's RMB deposit and loan
#: rate rules, 5 Jun 2026, https://www.cnfin.com/hb-lb/detail/20260605/4422766_1.html)
#: would move it to 365 (366 in leap years); this plugin keeps 360 until a
#: final rule is issued. Kuwait (KW), Saudi Arabia (SA) and North Macedonia
#: (MK) stay out: no central-bank or benchmark source is read for them.
CONVENTIONS: dict[str, RateConvention] = {
    **{area: ACT_360 for area in ("US", "XM", "CH", "SE", "DK", "CZ", "HU", "MX", "CL", "CO",
                                  "PE", "RO", "CN", "ID", "IS", "MA", "PH", "RS")},
    **{area: ACT_365 for area in ("GB", "CA", "AU", "NZ", "JP", "HK", "ZA", "KR", "NO", "PL",
                                  "MY", "TH", "IN", "IL", "RU", "TR")},
    "BR": BUS_252,
}  # fmt: skip
#: Why an economy's policy rate is read and not recorded.
NOT_CARRIED = "not carried: its money market's day count is not stated here"


@dataclass(frozen=True)
class Series:
    """One series the BIS publishes, and its record: the dataflow, the
    economy, the BIS's key for it (its record's symbol at `bis`), the record's
    type, its name, and the convention its rates are stated in (none for an
    index level, and none for a policy rate not carried)."""

    flow: str
    area: str
    name: str = ""
    central_bank: str = ""

    @property
    def key(self) -> str:
        """The BIS's key for the series, its record's symbol at `bis`:
        `WS_CBPOL.D.CA`, `WS_LONG_CPI.M.CA.628`."""
        if self.flow == CBPOL:
            return f"{CBPOL}.D.{self.area}"
        return f"{LONG_CPI}.M.{self.area}.{UNITS[LONG_CPI]}"

    @property
    def instrument_type(self) -> str:
        return INTEREST_RATE if self.flow == CBPOL else INDEX

    @property
    def kind(self) -> str:
        """What each value is recorded as: a policy rate a `fixing`, a CPI
        level a `level` (a DerivedSeries)."""
        return "fixing" if self.flow == CBPOL else "level"

    @property
    def convention(self) -> RateConvention | None:
        return CONVENTIONS.get(self.area) if self.flow == CBPOL else None

    @property
    def carried(self) -> bool:
        return self.flow != CBPOL or self.area in CONVENTIONS

    @property
    def identifier(self) -> tuple[str, str, str]:
        return ("symbol", self.key, SOURCE)

    @property
    def description(self) -> str:
        """The record's description, as the platform's seed would hold it."""
        if self.name:
            return self.name
        if self.flow == CBPOL:
            return f"Central bank policy rate, {self.area} (BIS)"
        return f"Long series on consumer prices, {self.area}, 2010 = 100 (BIS)"


def convention_said(series: Series) -> str:
    """A series' convention in words, for the Datasets page."""
    held = series.convention
    if series.flow != CBPOL:
        return "An index level, based 2010 = 100"
    if held is None:
        return NOT_CARRIED
    days = {"act_360": "actual/360", "act_365_fixed": "actual/365", "bus_252": "business/252"}
    how = "compounded annually" if held.compounding == "compounded" else "simple"
    return f"{days.get(str(held.day_count), str(held.day_count))}, {how}"
