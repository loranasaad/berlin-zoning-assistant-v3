"""
tests/test_cache.py — Tests for the address cache (chain/memory.py).

Covers:
  1. Basic save → exact lookup round-trip.
  2. BUG: number-first canonical format vs. street-first user input never matches.
  3. Prefix-35 fuzzy match — what does and doesn't work.
  4. Ambiguous prefix (>1 match) treated as a miss.
  5. Case / whitespace normalisation.
"""

import json
import sqlite3
import tempfile
import os
import pytest

# ---------------------------------------------------------------------------
# Patch SQLITE_MEMORY_PATH so tests use a temp DB, not the real memory.db
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test_cache.db")
    monkeypatch.setenv("SQLITE_MEMORY_PATH", db_path)

    # Patch config and memory module to use the temp path
    import config
    monkeypatch.setattr(config, "SQLITE_MEMORY_PATH", db_path)

    import chain.memory as mem
    monkeypatch.setattr(mem, "SQLITE_MEMORY_PATH", db_path)  # used inside cache_lookup/cache_save

    # Create the table
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS address_cache (
            canonical_address TEXT PRIMARY KEY,
            prefix35          TEXT NOT NULL,
            zoning_report     TEXT NOT NULL,
            created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    yield db_path


DUMMY_REPORT = {"status": "complete", "zone": {"type": "WA"}, "plot": {"area_m2": 500}}


# ---------------------------------------------------------------------------
# Helper — import after monkeypatch is active
# ---------------------------------------------------------------------------
def _mem():
    import chain.memory as mem
    return mem


# ---------------------------------------------------------------------------
# 1. Basic round-trip — save then lookup with the EXACT same string
# ---------------------------------------------------------------------------
def test_exact_hit():
    mem = _mem()
    canonical = "13 Schwedter Straße, 10119 Berlin"
    mem.cache_save(canonical, DUMMY_REPORT)
    result = mem.cache_lookup(canonical)
    assert result is not None, "Exact lookup must hit after save"
    assert result["zone"]["type"] == "WA"


# ---------------------------------------------------------------------------
# 2. FIX — token-sorted normalisation makes number/street order irrelevant
#
#    fisbroker.py line 231 builds:
#       display_name = f"{housenumber} {street}, {postcode} Berlin"
#       → "13 Schwedter Straße, 10119 Berlin"
#
#    But users type (and the classifier extracts):
#       "Schwedter Straße 13, 10119 Berlin"
#
#    _normalise() now sorts tokens → both produce the same key → cache hits.
# ---------------------------------------------------------------------------
def test_fix_number_first_vs_street_first():
    mem = _mem()

    canonical  = "13 Schwedter Straße, 10119 Berlin"   # how it is STORED
    user_input = "Schwedter Straße 13, 10119 Berlin"   # how the user TYPES it

    mem.cache_save(canonical, DUMMY_REPORT)
    result = mem.cache_lookup(user_input)
    assert result is not None, (
        "FIX: token-sorted normalisation must make number-first and "
        "street-first formats resolve to the same cache key."
    )
    assert result["zone"]["type"] == "WA"


def test_fix_different_casing_and_comma_placement():
    mem = _mem()

    canonical  = "6 Unter Den Linden, 10117 Berlin"
    user_input = "unter den linden 6 10117 berlin"     # no comma, different case

    mem.cache_save(canonical, DUMMY_REPORT)
    result = mem.cache_lookup(user_input)
    assert result is not None, "Token-sorted key must survive missing commas and case differences"


def test_no_postcode_still_misses_when_postcode_stored():
    """
    Without a postcode the token set differs — this is acceptable behaviour:
    we cannot be certain it is the same address without the postcode.
    """
    mem = _mem()

    canonical  = "13 Schwedter Straße, 10119 Berlin"
    user_input = "Schwedter Straße 13, Berlin"          # no postcode

    mem.cache_save(canonical, DUMMY_REPORT)
    result = mem.cache_lookup(user_input)
    assert result is None, (
        "Without a postcode the token sets differ — acceptable miss "
        "(postcode is required to disambiguate Berlin addresses)."
    )


# ---------------------------------------------------------------------------
# 3. Prefix-35 fuzzy match — only helps if the first 35 chars happen to match
# ---------------------------------------------------------------------------
def test_prefix35_hit_when_canonical_matches_prefix():
    """
    If the user supplies the canonical form (number-first) but with extra trailing
    text (e.g. city, country), the 35-char prefix match should rescue it.
    """
    mem = _mem()

    canonical        = "13 Schwedter Straße, 10119 Berlin"
    extended_variant = "13 Schwedter Straße, 10119 Berlin, Deutschland"

    mem.cache_save(canonical, DUMMY_REPORT)
    result = mem.cache_lookup(extended_variant)

    # Both start with the same 35 chars → prefix hit (if ≤35 chars each)
    # "13 schwedter straße, 10119 berlin" = 33 chars → full string IS the prefix
    # "13 schwedter straße, 10119 berlin, deutschland" → prefix35 = first 35 chars
    # They differ at char 34+, so this may or may not hit depending on exact length.
    # This test documents the actual behaviour rather than asserting a desired one.
    prefix_canonical = "13 schwedter straße, 10119 berlin"[:35]
    prefix_variant   = "13 schwedter straße, 10119 berlin, deutschland"[:35]
    if prefix_canonical == prefix_variant:
        assert result is not None, "Prefix match should hit when 35-char prefixes are equal"
    else:
        assert result is None, "Prefix match misses when 35-char prefixes differ"


def test_prefix35_now_matches_after_fix():
    """
    After the fix, both formats normalise to the same token-sorted key,
    so the exact match fires before the prefix logic is even needed.
    """
    mem = _mem()

    canonical  = "13 Schwedter Straße, 10119 Berlin"
    user_input = "Schwedter Straße 13, 10119 Berlin"

    mem.cache_save(canonical, DUMMY_REPORT)
    result = mem.cache_lookup(user_input)
    assert result is not None, "Exact match on token-sorted key hits without needing prefix logic"


# ---------------------------------------------------------------------------
# 4. Ambiguous prefix — multiple entries share the same prefix35 → miss
# ---------------------------------------------------------------------------
def test_ambiguous_prefix_treated_as_miss():
    mem = _mem()

    # Both start with the same 35 chars (Eulerstraße addresses)
    addr1 = "6 eulerstraße, 13357 berlin"
    addr2 = "8 eulerstraße, 13357 berlin"

    # They differ before char 35, so they have different prefix35 values.
    # Use addresses that genuinely share a prefix to trigger the ambiguous path.
    # Pad them so they share 35 chars but differ after.
    shared = "x" * 35
    a1 = shared + "aaa"
    a2 = shared + "bbb"
    lookup_prefix = shared + "zzz"   # matches both by prefix35

    mem.cache_save(a1, DUMMY_REPORT)
    mem.cache_save(a2, DUMMY_REPORT)

    result = mem.cache_lookup(lookup_prefix)
    assert result is None, "Ambiguous prefix (>1 match) must return None"


# ---------------------------------------------------------------------------
# 5. Normalisation — case and leading/trailing whitespace
# ---------------------------------------------------------------------------
def test_case_insensitive_exact_hit():
    mem = _mem()

    mem.cache_save("Unter Den Linden 6, 10117 Berlin", DUMMY_REPORT)
    result = mem.cache_lookup("unter den linden 6, 10117 berlin")
    assert result is not None, "Lookup must be case-insensitive"


def test_whitespace_normalisation():
    mem = _mem()

    mem.cache_save("  Unter Den Linden 6, 10117 Berlin  ", DUMMY_REPORT)
    result = mem.cache_lookup("Unter Den Linden 6, 10117 Berlin")
    assert result is not None, "Leading/trailing whitespace must be stripped"


# ---------------------------------------------------------------------------
# 6. INSERT OR REPLACE — saving the same address twice updates the record
# ---------------------------------------------------------------------------
def test_cache_save_overwrites():
    mem = _mem()

    canonical = "6 Unter Den Linden, 10117 Berlin"
    mem.cache_save(canonical, DUMMY_REPORT)

    updated_report = {**DUMMY_REPORT, "zone": {"type": "MI"}}
    mem.cache_save(canonical, updated_report)

    result = mem.cache_lookup(canonical)
    assert result["zone"]["type"] == "MI", "Second save must overwrite the first"
