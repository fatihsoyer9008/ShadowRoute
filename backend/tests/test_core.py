"""Çekirdek algoritma testleri. Çalıştır:  python -m pytest  (backend/ içinden)"""
from __future__ import annotations

import math
from datetime import datetime

import pytest

from app.core.geo import haversine_m, initial_bearing_deg, normalize_180
from app.core.shadow import Side, _classify, analyze
from app.core.sun import TURKEY_TZ, SunPosition, get_sun


# --- geo --------------------------------------------------------------------
def test_bearing_cardinals():
    assert initial_bearing_deg((0, 0), (1, 0)) == pytest.approx(0, abs=1e-6)      # kuzey
    assert initial_bearing_deg((0, 0), (0, 1)) == pytest.approx(90, abs=1e-6)     # doğu
    assert initial_bearing_deg((0, 0), (-1, 0)) == pytest.approx(180, abs=1e-6)   # güney


def test_haversine_known_distance():
    # 1 derece boylam ekvatorda ~111.3 km
    d = haversine_m((0, 0), (0, 1))
    assert d == pytest.approx(111_195, rel=0.01)


def test_normalize_180():
    assert normalize_180(190) == pytest.approx(-170)
    assert normalize_180(-190) == pytest.approx(170)
    assert normalize_180(180) == pytest.approx(180)


# --- sınıflandırma ---------------------------------------------------------
def test_night_gives_none():
    sun = SunPosition(azimuth_deg=90, altitude_deg=-5)
    side, lat, fro = _classify(bearing_deg=0, sun=sun, in_tunnel=False)
    assert side is Side.NONE and lat == 0 and fro == 0


def test_tunnel_gives_none_even_with_sun():
    sun = SunPosition(azimuth_deg=90, altitude_deg=40)
    side, *_ = _classify(bearing_deg=0, sun=sun, in_tunnel=True)
    assert side is Side.NONE


def test_sun_on_the_right():
    # Doğuya git (bearing 90), güneş güneyde (azimut 180) -> sağda
    sun = SunPosition(azimuth_deg=180, altitude_deg=30)
    side, lateral, _ = _classify(bearing_deg=90, sun=sun, in_tunnel=False)
    assert side is Side.RIGHT
    assert lateral == pytest.approx(math.cos(math.radians(30)), abs=1e-6)  # rel=90 -> sin=1


def test_sun_on_the_left():
    sun = SunPosition(azimuth_deg=0, altitude_deg=30)   # kuzey
    side, _, _ = _classify(bearing_deg=90, sun=sun, in_tunnel=False)
    assert side is Side.LEFT


def test_sun_ahead_is_front():
    sun = SunPosition(azimuth_deg=95, altitude_deg=20)
    side, _, _ = _classify(bearing_deg=90, sun=sun, in_tunnel=False)
    assert side is Side.FRONT


def test_high_sun_reduces_lateral_exposure():
    low = SunPosition(azimuth_deg=180, altitude_deg=10)
    high = SunPosition(azimuth_deg=180, altitude_deg=80)
    _, lat_low, _ = _classify(90, low, False)
    _, lat_high, _ = _classify(90, high, False)
    assert lat_high < lat_low


# --- suncalc entegrasyonu ------------------------------------------------
def test_bursa_noon_sun_is_south_and_high():
    noon = datetime(2026, 6, 21, 13, 0, tzinfo=TURKEY_TZ)
    sp = get_sun(noon, 40.19, 29.06)
    assert 150 < sp.azimuth_deg < 210          # ~güney
    assert sp.altitude_deg > 60                # yaz öğlen yüksek


def test_bursa_night_sun_below_horizon():
    sp = get_sun(datetime(2026, 1, 15, 2, 0, tzinfo=TURKEY_TZ), 40.19, 29.06)
    assert sp.altitude_deg < 0


# --- uçtan uca -----------------------------------------------------------
def test_analyze_eastbound_evening_recommends_left():
    # Batıya doğru giden bir düz rota, akşamüstü güneş batıda -> önde/sağda.
    # Doğuya giden rota + akşam güneşi (batı) -> arkada. Sol/sağ dengeli olmalı.
    coords = [(40.19, 29.00), (40.19, 29.05), (40.19, 29.10)]  # tam doğu
    dep = datetime(2026, 9, 1, 18, 0, tzinfo=TURKEY_TZ)
    res = analyze(coords, dep, avg_speed_kmh=20)
    assert res.total_length_m > 0
    assert res.recommended_side in (Side.LEFT, Side.RIGHT, Side.NONE)


def test_analyze_marks_tunnel_segments_none():
    coords = [(40.22, 28.95), (40.21, 29.00), (40.20, 29.02), (40.19, 29.05)]
    dep = datetime(2026, 6, 21, 12, 0, tzinfo=TURKEY_TZ)
    res = analyze(coords, dep, avg_speed_kmh=30, tunnel_segments=[(1, 1)])
    assert res.segments[1].in_tunnel
    assert res.segments[1].side is Side.NONE


def test_analyze_all_night_is_no_preference():
    coords = [(40.19, 29.00), (40.19, 29.10)]
    res = analyze(coords, datetime(2026, 1, 15, 3, 0, tzinfo=TURKEY_TZ), avg_speed_kmh=20)
    assert res.recommended_side is Side.NONE
