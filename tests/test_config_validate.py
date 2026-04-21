"""Tests for settings.yaml scalar validation."""

import pytest

from app.config._validate import SettingsValidationError, validate


def test_accepts_empty_dict():
    validate({})


def test_accepts_well_formed_values():
    validate({
        "embeddings": {"chunk_size": 1500, "chunk_overlap": 150},
        "retrieval": {
            "top_k": 5,
            "score_threshold": 0.3,
            "hybrid_search": True,
            "bm25_weight": 0.5,
        },
        "llm": {"temperature": 0.3, "max_tokens": 4096},
        "server": {"host": "127.0.0.1", "port": 9713},
        "logging": {"level": "INFO"},
    })


def test_rejects_string_where_number_expected():
    with pytest.raises(SettingsValidationError) as exc_info:
        validate({"llm": {"temperature": "high"}})
    assert "llm.temperature" in str(exc_info.value)


def test_rejects_out_of_range():
    with pytest.raises(SettingsValidationError) as exc_info:
        validate({"server": {"port": 0}})
    assert "server.port" in str(exc_info.value)


def test_rejects_bool_for_int_field():
    with pytest.raises(SettingsValidationError):
        validate({"retrieval": {"top_k": True}})


def test_rejects_int_for_bool_field():
    with pytest.raises(SettingsValidationError):
        validate({"retrieval": {"hybrid_search": 1}})


def test_rejects_unknown_log_level():
    with pytest.raises(SettingsValidationError):
        validate({"logging": {"level": "TRACE"}})


def test_tolerates_unknown_keys():
    # Arbitrary plugin / future-version keys must not error.
    validate({
        "plugins": {"buckets": {"enabled": True, "custom_field": 42}},
        "services": {"deep_research": {"iterations": 3}},
        "totally_new_section": {"x": 1},
    })
