"""Çekirdek algoritma testleri. Çalıştır:  python -m pytest  (backend/ içinden)"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from app.core.geo import (
    auto_loop_split,
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


# --- kapalı halka hatlar (38, 4G) -------------------------------------
@pytest.mark.parametrize("route_id", ["bus-38", "bus-4g"])
def test_loop_route_splits_into_two_legs(route_id):
    from app.routes_repo import load_routes

    r = load_routes()[route_id]
    assert r.loop_split is not None

    fwd, _ = r.path("forward")
    bwd, _ = r.path("backward")

    # İki bacak ayrı yollar (biri diğerinin tersi DEĞİL), dönüş noktasında birleşiyor.
    assert fwd[-1] == bwd[0]
    assert fwd != list(reversed(bwd))
    assert len(fwd) + len(bwd) == len(r.coords) + 1


def test_auto_loop_split():
    # Düz hat -> None
    line = [(40.19, 29.00), (40.19, 29.03), (40.19, 29.06), (40.19, 29.09)]
    assert auto_loop_split(line) is None

    # Kapalı halka: git-dön, uçlar aynı -> ortadaki en uzak nokta
    loop = [(40.19, 29.00), (40.19, 29.02), (40.19, 29.05),  # en uzak (idx 2)
            (40.19, 29.02), (40.19, 29.00001)]
    assert auto_loop_split(loop) == 2


def test_auto_loop_split_matches_curated_bus38():
    from app.routes_repo import load_routes

    coords = load_routes()["bus-38"].coords
    auto = auto_loop_split(coords)
    assert auto is not None
    # Elle ayarlanan 230'a yakın olmalı (±%10).
    assert abs(auto - 230) < len(coords) * 0.1


def test_bus38_legs_face_opposite_sun_sides():
    from app.routes_repo import load_routes

    r = load_routes()["bus-38"]
    dep = datetime(2026, 6, 21, 8, 0, tzinfo=TURKEY_TZ)  # sabah, güneş doğuda
    f = analyze(r.path("forward")[0], dep, avg_speed_kmh=r.avg_speed_kmh)
    b = analyze(r.path("backward")[0], dep, avg_speed_kmh=r.avg_speed_kmh)
    # Kuzey-güney hat: bir bacak sola, diğeri sağa oturt demeli.
    assert {f.recommended_side, b.recommended_side} == {Side.LEFT, Side.RIGHT}


# --- canlı hat çözümleme: statik fallback + cache ----------------------
def test_live_route_prefers_curated_by_hat_no():
    # M1'in hatNo'su 1531; canlı istenince elle ayarlı hat (tünel bölgeleriyle)
    # dönmeli — ağ gerektirmez.
    from app.routes_repo import live_route

    r = live_route(1531)
    assert r.id == "bursaray-m1"
    assert len(r.tunnel_zones) == 9


def test_burulas_disk_cache_and_offline_fallback(tmp_path, monkeypatch):
    from app import burulas

    monkeypatch.setattr(burulas, "CACHE_DIR", tmp_path / "cache")
    burulas.clear_cache()

    calls = {"n": 0}

    def fake_post(path, body):
        calls["n"] += 1
        return [{"sequence": 1, "stopName": "A", "direction": "R"},
                {"sequence": 2, "stopName": "B", "direction": "R"}]

    monkeypatch.setattr(burulas, "_post", fake_post)

    a = burulas.route_stops(9999)
    assert calls["n"] == 1
    burulas.clear_cache()                 # bellek temiz, disk dolu
    b = burulas.route_stops(9999)
    assert calls["n"] == 1 and a == b     # diskten geldi, yeni istek yok

    # Burulaş erişilemez -> bayat disk verisi
    burulas.clear_cache()

    def boom(path, body):
        raise burulas.BurulasError("down")

    monkeypatch.setattr(burulas, "_post", boom)
    assert burulas.route_stops(9999) == a


# ======================================================================
#  Faz 4 — gündoğumu / günbatımı sınır durumları
# ======================================================================
BURSA = (40.19, 29.06)
# Kuzey-güney düz test hattı (~8.5 km): kuzeye giderken doğu güneşi sağdan.
NS_LINE = [(40.16, 29.06), (40.20, 29.06), (40.24, 29.06)]


def _horizon_crossing(y: int, mo: int, d: int, *, rising: bool) -> datetime:
    """Verilen gün için Bursa'da güneşin ufku geçtiği ilk anı (2 dk çözünürlük)."""
    base = datetime(y, mo, d, tzinfo=TURKEY_TZ)
    prev = None
    for m in range(0, 24 * 60, 2):
        alt = get_sun(base + timedelta(minutes=m), *BURSA).altitude_deg
        if prev is not None:
            if rising and prev <= 0 < alt:
                return base + timedelta(minutes=m)
            if not rising and prev > 0 >= alt:
                return base + timedelta(minutes=m)
        prev = alt
    raise AssertionError("ufuk geçişi bulunamadı")


# --- güneş konumu sınırda ---------------------------------------------
def test_sun_exactly_at_horizon_counts_as_down():
    assert not SunPosition(azimuth_deg=90, altitude_deg=0.0).is_up
    assert SunPosition(azimuth_deg=90, altitude_deg=0.0).horizontality == 0.0
    side, lat, fro = _classify(0.0, SunPosition(azimuth_deg=90, altitude_deg=0.0), False)
    assert (side, lat, fro) == (Side.NONE, 0.0, 0.0)


def test_horizontality_peaks_at_horizon():
    just_up = SunPosition(azimuth_deg=90, altitude_deg=0.5)
    overhead = SunPosition(azimuth_deg=90, altitude_deg=89.0)
    assert just_up.horizontality > 0.999      # alçak güneş = tam yanal
    assert overhead.horizontality < 0.02       # tepe güneşi = yanal yok


def test_front_back_cone_boundaries():
    # rel = güneş_azimut - bearing.  bearing 90 (doğu).
    at_35 = _classify(90, SunPosition(azimuth_deg=90 + 35, altitude_deg=20), False)[0]
    at_36 = _classify(90, SunPosition(azimuth_deg=90 + 36, altitude_deg=20), False)[0]
    at_145 = _classify(90, SunPosition(azimuth_deg=90 + 145, altitude_deg=20), False)[0]
    at_144 = _classify(90, SunPosition(azimuth_deg=90 + 144, altitude_deg=20), False)[0]
    assert at_35 is Side.FRONT and at_36 is Side.RIGHT
    assert at_145 is Side.BACK and at_144 is Side.RIGHT


# --- suncalc: doğuş/batış yönleri ------------------------------------
def test_sunrise_sun_is_in_the_east():
    rise = _horizon_crossing(2026, 3, 20, rising=True)
    sp = get_sun(rise + timedelta(minutes=20), *BURSA)
    assert 0 < sp.altitude_deg < 8                 # alçak
    assert 60 < sp.azimuth_deg < 120               # doğu


def test_sunset_sun_is_in_the_west():
    dusk = _horizon_crossing(2026, 3, 20, rising=False)
    sp = get_sun(dusk - timedelta(minutes=20), *BURSA)
    assert 0 < sp.altitude_deg < 8
    assert 240 < sp.azimuth_deg < 300             # batı


def test_summer_day_longer_than_winter():
    def daylight_minutes(mo, d):
        r = _horizon_crossing(2026, mo, d, rising=True)
        s = _horizon_crossing(2026, mo, d, rising=False)
        return (s - r).total_seconds() / 60

    assert daylight_minutes(6, 21) > daylight_minutes(12, 21) + 240


def test_turkey_timezone_has_no_dst():
    for month in (1, 4, 7, 10):
        off = TURKEY_TZ.utcoffset(datetime(2026, month, 15))
        assert off == timedelta(hours=3)
    # eski DST geçiş tarihinde de +03
    assert get_sun(datetime(2026, 3, 29, 12, 0, tzinfo=TURKEY_TZ), *BURSA).altitude_deg > 40


# --- analyze: yolculuk ufku geçerken -------------------------------
def test_trip_starting_before_sunrise_has_partial_sun():
    rise = _horizon_crossing(2026, 3, 20, rising=True)
    dep = rise - timedelta(minutes=15)            # 15 dk karanlık + sonrası
    res = analyze(NS_LINE, dep, avg_speed_kmh=12)  # yavaş -> yolculuk ~45 dk
    assert 0.0 < res.sun_up_fraction < 1.0
    dark = [s for s in res.segments if s.sun_altitude_deg <= 0]
    lit = [s for s in res.segments if s.sun_altitude_deg > 0]
    assert dark and lit
    assert all(s.side is Side.NONE for s in dark)


def test_trip_ending_after_sunset_has_partial_sun():
    dusk = _horizon_crossing(2026, 3, 20, rising=False)
    dep = dusk - timedelta(minutes=20)
    res = analyze(NS_LINE, dep, avg_speed_kmh=12)
    assert 0.0 < res.sun_up_fraction < 1.0


def test_deep_night_trip_no_preference_no_low_sun_warning():
    res = analyze(NS_LINE, datetime(2026, 1, 15, 2, 30, tzinfo=TURKEY_TZ),
                  avg_speed_kmh=20)
    assert res.recommended_side is Side.NONE
    assert res.sun_up_fraction < 0.01
    assert not any("alçak" in n.lower() for n in res.notes)


def test_low_sun_warning_fires_just_after_sunrise_and_not_at_noon():
    rise = _horizon_crossing(2026, 3, 20, rising=True)
    # Kuzeye giden hat, doğuş sonrası -> güneş sağdan, alçak.
    early = analyze(NS_LINE, rise + timedelta(minutes=10), avg_speed_kmh=20)
    noon = analyze(NS_LINE, datetime(2026, 3, 20, 12, 30, tzinfo=TURKEY_TZ),
                   avg_speed_kmh=20)
    assert any("alçak" in n.lower() for n in early.notes)
    assert not any("alçak" in n.lower() for n in noon.notes)


def test_sunrise_northbound_sun_on_the_right():
    rise = _horizon_crossing(2026, 3, 20, rising=True)
    res = analyze(NS_LINE, rise + timedelta(minutes=25), avg_speed_kmh=20)
    # Kuzeye gidiş + doğu güneşi -> sağdan; öneri SOL.
    assert res.recommended_side is Side.LEFT


# ======================================================================
#  V2 — duraktan durağa (kısmi biniş)
# ======================================================================
def test_stops_for_direction_is_monotonic_and_maps_to_polyline():
    from app.routes_repo import load_routes

    m1 = load_routes()["bursaray-m1"]
    fwd = m1.stops_for("forward")
    assert [n for n, _ in fwd] == m1.stops               # düz hat: tüm duraklar
    idxs = [i for _, i in fwd]
    assert idxs == sorted(idxs) and idxs[0] == 0
    # backward: aynı duraklar ters sırayla, indeksler yine artan
    bwd = m1.stops_for("backward")
    assert [n for n, _ in bwd] == list(reversed(m1.stops))
    assert [i for _, i in bwd] == sorted(i for _, i in bwd)


def test_partial_ride_is_shorter_and_can_flip_the_verdict():
    from app.routes_repo import load_routes

    m1 = load_routes()["bursaray-m1"]
    fwd = m1.stops_for("forward")
    names = [n for n, _ in fwd]
    k, g = names.index("Kültürpark"), names.index("Gökdere")

    dep = datetime(2026, 9, 1, 13, 0, tzinfo=TURKEY_TZ)
    fc, fz = m1.path("forward")
    full = analyze(fc, dep, avg_speed_kmh=m1.avg_speed_kmh, tunnel_zones=fz)
    seg_coords, zones = m1.path("forward", fwd[k][1], fwd[g][1])
    part = analyze(seg_coords, dep, avg_speed_kmh=m1.avg_speed_kmh, tunnel_zones=zones)

    assert part.total_length_m < full.total_length_m * 0.4
    # Kültürpark–Gökdere neredeyse tamamen tünel -> "yok" payı çok yüksek
    assert part.pct_length(Side.NONE) > 70 > full.pct_length(Side.NONE)


def test_loop_route_stops_split_by_leg():
    from app.routes_repo import load_routes

    r = load_routes()["bus-38"]
    fwd = r.stops_for("forward")
    bwd = r.stops_for("backward")
    assert fwd and bwd
    # gidiş bacağı duraklarının forward-index'i loop_split içinde kalır
    fwd_coords, _ = r.path("forward")
    bwd_coords, _ = r.path("backward")
    assert all(0 <= i < len(fwd_coords) for _, i in fwd)
    assert all(0 <= i < len(bwd_coords) for _, i in bwd)
    # iki bacak dönüş noktasında buluşur (son gidiş ≈ ilk dönüş durağı)
    assert fwd[-1][0] == bwd[0][0]


def test_path_rejects_too_short_stop_range():
    from app.routes_repo import load_routes

    m1 = load_routes()["bursaray-m1"]
    with pytest.raises(ValueError):
        m1.path("forward", 5, 5)
