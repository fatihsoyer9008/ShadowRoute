"""Çekirdek algoritma testleri. Çalıştır:  python -m pytest  (backend/ içinden)"""
from __future__ import annotations

import math
from datetime import datetime

import pytest

from app.core.geo import (
    haversine_m,
    initial_bearing_deg,
    normalize_180,
    rdp_simplify,
    resample_polyline,
    smooth_route,
)
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


def test_analyze_marks_tunnel_zone_none():
    coords = [(40.22, 28.95), (40.21, 29.00), (40.20, 29.02), (40.19, 29.05)]
    dep = datetime(2026, 6, 21, 12, 0, tzinfo=TURKEY_TZ)
    # (40.205, 29.01) çevresi 800 m -> ikinci segmentin ortası bu dairede.
    res = analyze(coords, dep, avg_speed_kmh=30,
                  tunnel_zones=[(40.205, 29.01, 800.0)], resample_step_m=None)
    tunnel = [s for s in res.segments if s.in_tunnel]
    assert tunnel, "tünel bölgesindeki en az bir segment işaretlenmeli"
    assert all(s.side is Side.NONE for s in tunnel)
    # Daireden uzak segmentler etkilenmemeli.
    assert any(not s.in_tunnel for s in res.segments)


# --- polyline yumuşatma ------------------------------------------------
def test_rdp_drops_collinear_points():
    line = [(0.0, 0.0), (0.0, 0.5), (0.0, 1.0), (0.0, 1.5)]
    assert rdp_simplify(line, 10.0) == [(0.0, 0.0), (0.0, 1.5)]


def test_rdp_keeps_real_corner():
    corner = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    assert rdp_simplify(corner, 10.0) == corner


def test_rdp_removes_jitter_spike():
    # Düz doğu hattı + ortada ~5 m'lik kuzey sıçraması -> RDP atmalı.
    jitter = [(40.19, 29.00), (40.190045, 29.005), (40.19, 29.01)]
    out = rdp_simplify(jitter, 25.0)
    assert out == [(40.19, 29.00), (40.19, 29.01)]


def test_resample_uniform_spacing():
    pts = resample_polyline([(40.19, 29.00), (40.19, 29.02)], 50.0)
    gaps = [haversine_m(a, b) for a, b in zip(pts, pts[1:])]
    assert max(gaps) <= 55.0
    assert pts[0] == (40.19, 29.00) and pts[-1] == (40.19, 29.02)


def test_smooth_route_denoises_but_keeps_shape():
    raw = [(40.19, 29.00), (40.1901, 29.0009), (40.19, 29.002),
           (40.1899, 29.0031), (40.19, 29.004)]
    out = smooth_route(raw, simplify_epsilon_m=25.0, resample_step_m=40.0)
    assert len(out) < 60
    assert haversine_m(out[0], raw[0]) < 1.0
    assert haversine_m(out[-1], raw[-1]) < 1.0


# --- gerçek BursaRay M1 / M2 hatları + tünel bölgeleri ------------------
@pytest.mark.parametrize(
    "route_id, band",
    [("bursaray-m1", (0.20, 0.35)), ("bursaray-m2", (0.15, 0.28))],
)
def test_bursaray_tunnel_zones(route_id, band):
    from app.routes_repo import load_routes

    route = load_routes()[route_id]
    dep = datetime(2026, 6, 21, 13, 0, tzinfo=TURKEY_TZ)  # tepe güneş
    lo, hi = band

    for direction in ("forward", "backward"):
        coords, zones = route.path(direction)
        res = analyze(coords, dep, avg_speed_kmh=route.avg_speed_kmh, tunnel_zones=zones)

        assert lo <= res.pct_length(Side.NONE) / 100 <= hi, (route_id, direction)

        # Merinos–Demirtaşpaşa ortak çekirdek tüneli boyunca güneş etkisi sıfır.
        core = [
            s for s in res.segments
            if 40.186 <= s.mid[0] <= 40.199 and 29.051 <= s.mid[1] <= 29.068
        ]
        assert core, (route_id, direction)
        assert all(s.side is Side.NONE and s.in_tunnel for s in core), (route_id, direction)

        # Kültürpark (hemzemin) civarı tünel sayılmamalı.
        kulturpark = [s for s in res.segments
                      if haversine_m(s.mid, (40.20033, 29.0407)) < 150]
        assert kulturpark and not any(s.in_tunnel for s in kulturpark), (route_id, direction)


def test_m1_m2_share_the_central_tunnel_zones():
    from app.routes_repo import load_routes

    routes = load_routes()
    m1 = set(routes["bursaray-m1"].tunnel_zones)
    m2 = set(routes["bursaray-m2"].tunnel_zones)
    shared = m1 & m2
    # Acemler (1) + merkez tüneli (7) = 8 ortak bölge, tek yerde tanımlı.
    assert len(shared) == 8
    assert (40.213033, 29.014883, 470) in shared  # Acemler


def test_analyze_all_night_is_no_preference():
    coords = [(40.19, 29.00), (40.19, 29.10)]
    res = analyze(coords, datetime(2026, 1, 15, 3, 0, tzinfo=TURKEY_TZ), avg_speed_kmh=20)
    assert res.recommended_side is Side.NONE
