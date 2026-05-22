"""Tests for the CatRequestCache TTL in-process cache."""
import time

import pytest


def test_cat_request_cache_calls_db_on_first_get(monkeypatch):
    import logic.cat_request_cache as crc
    from logic.cat_request_cache import CatRequestCache

    expected_payload = ({"CourseA": ["Cat1"]}, {"CourseA": {"Cat1": 3}})
    call_count = [0]

    def fake_retrieve(session):
        call_count[0] += 1
        return expected_payload

    monkeypatch.setattr(crc, "retrieve_cat_request_payload", fake_retrieve)

    cache = CatRequestCache(ttl=60)
    result = cache.get(object())  # session argument not used by fake_retrieve

    assert result == expected_payload
    assert call_count[0] == 1


def test_cat_request_cache_returns_cached_result_on_second_get(monkeypatch):
    import logic.cat_request_cache as crc
    from logic.cat_request_cache import CatRequestCache

    expected_payload = ({"CourseA": ["Cat1"]}, {"CourseA": {"Cat1": 3}})
    call_count = [0]

    def fake_retrieve(session):
        call_count[0] += 1
        return expected_payload

    monkeypatch.setattr(crc, "retrieve_cat_request_payload", fake_retrieve)

    cache = CatRequestCache(ttl=60)
    cache.get(object())  # prime the cache
    result = cache.get(object())  # should hit cache

    assert result == expected_payload
    assert call_count[0] == 1  # DB only called once


def test_cat_request_cache_refreshes_after_ttl_expires(monkeypatch):
    import logic.cat_request_cache as crc
    from logic.cat_request_cache import CatRequestCache

    expected_payload = ({"CourseA": ["Cat1"]}, {"CourseA": {"Cat1": 3}})
    call_count = [0]

    def fake_retrieve(session):
        call_count[0] += 1
        return expected_payload

    monkeypatch.setattr(crc, "retrieve_cat_request_payload", fake_retrieve)

    cache = CatRequestCache(ttl=60)
    cache.get(object())  # prime the cache

    # Force TTL expiry by rewinding the internal clock
    cache._expires_at = time.monotonic() - 1

    cache.get(object())  # should call DB again

    assert call_count[0] == 2
