"""The BIS's SDMX-CSV read as written: values kept as text, a missing value
no value, a line in another unit not read, and anything else refused."""

from __future__ import annotations

from datetime import date

import pytest

from bis.sdmx import CBPOL, LONG_CPI, NotSdmx, parse, period_day

HEADER = (
    "STRUCTURE,STRUCTURE_ID,ACTION,FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE,UNIT_MEASURE,UNIT_MULT,"
    "TITLE,SOURCE_REF,OBS_STATUS"
)


def test_values_as_written() -> None:
    text = "\n".join(
        [
            HEADER,
            "dataflow,BIS:WS_CBPOL(1.0),I,D,CA,2026-11-16,2.50,368,0,"
            '"Policy, Canada",Bank of Canada,A',
            "dataflow,BIS:WS_CBPOL(1.0),I,D,CA,2026-11-15,NaN,368,0,,,M",
            "dataflow,BIS:WS_CBPOL(1.0),I,D,GB,2026-11-16,4,999,0,,,A",
            "dataflow,BIS:WS_CBPOL(1.0),I,D,GB,2026-11-17,n/a,368,0,,,A",
        ]
    )
    read = parse(text, CBPOL)
    assert [(o.area, o.day, o.text) for o in read.observations] == [
        ("CA", date(2026, 11, 16), "2.50")
    ]
    assert read.described["CA"].title == "Policy, Canada"
    assert read.described["CA"].source == "Bank of Canada"
    assert len(read.unread) == 2 and "unit '999'" in read.unread[0]


def test_a_month_is_its_first_day() -> None:
    assert period_day("2026-09") == date(2026, 9, 1)
    text = (
        "STRUCTURE,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"
        "dataflow,GB,628,2026-09,161.125606,0\n"
    )
    read = parse(text, LONG_CPI)
    assert read.observations[0].day == date(2026, 9, 1)
    assert read.observations[0].text == "161.125606"


def test_an_empty_answer_and_another_answer() -> None:
    assert parse("", CBPOL).observations == []
    with pytest.raises(NotSdmx):
        parse("<html>Service unavailable</html>", CBPOL)
