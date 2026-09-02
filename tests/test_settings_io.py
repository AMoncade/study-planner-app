"""Tests de la persistance des paramètres du moteur (§4.9 <-> table settings)."""

from datetime import time

import pytest

from planner.config import EngineSettings, load_engine_settings, save_engine_settings
from planner.storage.db import connect


@pytest.fixture()
def conn():
    c = connect(":memory:")
    yield c
    c.close()


def test_defaults_when_nothing_saved(conn):
    s = load_engine_settings(conn)
    assert s == EngineSettings()


def test_roundtrip(conn):
    s = EngineSettings()
    s.alpha = 0.75
    s.wake_start = time(7, 30)
    s.b_type["quiz"] = 2.0
    s.hour_penalty[22] = 3.0
    s.h_jour_max_week = 5.0
    save_engine_settings(conn, s)
    loaded = load_engine_settings(conn)
    assert loaded.alpha == 0.75
    assert loaded.wake_start == time(7, 30)
    assert loaded.b_type["quiz"] == 2.0
    assert loaded.hour_penalty[22] == 3.0
    assert loaded.h_jour_max_week == 5.0


def test_corrupt_value_falls_back_to_defaults(conn):
    from planner.config import SETTINGS_KEY
    from planner.storage import repositories as repos

    repos.set_setting(conn, SETTINGS_KEY, "{pas du json")
    assert load_engine_settings(conn) == EngineSettings()
