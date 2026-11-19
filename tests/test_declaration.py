"""The catalogue, from code, as the deployment approves it."""

from __future__ import annotations

from meridian.plugin.v1 import operations_pb2 as ops

from bis.declaration import DECLARATION
from bis.declared import BIS_CBPOL_DATASET, BIS_LONG_CPI_DATASET, CBPOL_TERMS, CPI_TERMS


def test_two_datasets_rates_and_the_bis_figures() -> None:
    # Their keys proposed with 0.1.0 (the product owner approves a dataset name).
    assert [d.key for d in DECLARATION.catalogue] == ["bis_cbpol", "bis_long_cpi"]
    assert list(BIS_CBPOL_DATASET.data_types) == ["meridian.v1.Rate"]
    assert list(BIS_LONG_CPI_DATASET.data_types) == ["meridian.v1.DerivedSeries"]
    for dataset in DECLARATION.catalogue:
        modes = [ops.ObservationMode.Name(m) for m in dataset.modes]
        assert modes == ["OBSERVATION_MODE_PUSH", "OBSERVATION_MODE_PULL"]
        assert dataset.day_time_zone == "UTC" and dataset.day_end_minute == 0
        assert not dataset.calendar_id and not dataset.venue_id and not dataset.aggregator
        assert dataset.vendor == "Bank for International Settlements"
    assert BIS_CBPOL_DATASET.cadence == 86_400 and BIS_CBPOL_DATASET.history == 29_500
    assert BIS_LONG_CPI_DATASET.history == 0


def test_the_bis_terms_in_words_and_a_gap_asked_again() -> None:
    # Contract 30 (ruling 1032): the BIS's terms described, no licence; the
    # API serves every past period, so a gap is asked again (W10.14).
    assert BIS_CBPOL_DATASET.terms_and_pricing == CBPOL_TERMS
    assert BIS_LONG_CPI_DATASET.terms_and_pricing == CPI_TERMS
    for dataset in DECLARATION.catalogue:
        said = dataset.terms_and_pricing
        assert "cited as the source" in said and "must not add a charge" in said
        assert len(said) <= 2000
        assert dataset.gap_recovery == "backfill" and not dataset.sessions_calendar_id


def test_the_answers_are_kept_in_storage() -> None:
    assert DECLARATION.storage is not None
    assert [k.name for k in DECLARATION.storage.kinds] == ["responses"]
