"""Coğrafi yardımcılar: iki nokta arası mesafe ve pusula yönü (heading).

Koordinatlar her yerde (lat, lon) ikilisi olarak, derece cinsinden.
GeoJSON [lon, lat] sırasını kullandığı için dosya okuurken çeviriyoruz.
"""
from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0

Point = tuple[float, float]  # (lat, lon)


def haversine_m(a: Point, b: Point) -> float:
    """İki nokta arası büyük daire mesafesi (metre)."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def initial_bearing_deg(a: Point, b: Point) -> float:
    """a -> b yönünün pusula açısı: 0 = Kuzey, 90 = Doğu, saat yönünde. [0, 360)"""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def midpoint(a: Point, b: Point) -> Point:
    """Kısa segmentler için düz ortalama yeterli (güneş konumu segment boyunca ~sabit)."""
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def normalize_180(deg: float) -> float:
    """Açıyı (-180, 180] aralığına indirger."""
    d = (deg + 180.0) % 360.0 - 180.0
    return d + 360.0 if d <= -180.0 else d


def _local_xy(p: Point, ref_lat_deg: float) -> tuple[float, float]:
    """Küçük bölgeler için eşdikdörtgen (equirectangular) düzlem izdüşümü, metre."""
    lat = math.radians(p[0])
    lon = math.radians(p[1])
    x = lon * math.cos(math.radians(ref_lat_deg)) * EARTH_RADIUS_M
    y = lat * EARTH_RADIUS_M
    return x, y


def _perp_distance_m(p: Point, a: Point, b: Point) -> float:
    """p noktasının a-b doğru parçasına dik uzaklığı (metre)."""
    ref = a[0]
    px, py = _local_xy(p, ref)
    ax, ay = _local_xy(a, ref)
    bx, by = _local_xy(b, ref)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def rdp_simplify(coords: list[Point], epsilon_m: float) -> list[Point]:
    """Douglas–Peucker: GPS titremesini ve gereksiz ~doğrusal noktaları atar,
    gerçek dönüşleri korur. epsilon_m küçüldükçe daha çok nokta kalır."""
    if len(coords) < 3 or epsilon_m <= 0:
        return list(coords)

    keep = [False] * len(coords)
    keep[0] = keep[-1] = True
    stack = [(0, len(coords) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        dmax, idx = 0.0, lo
        a, b = coords[lo], coords[hi]
        for i in range(lo + 1, hi):
            d = _perp_distance_m(coords[i], a, b)
            if d > dmax:
                dmax, idx = d, i
        if dmax > epsilon_m:
            keep[idx] = True
            stack.append((lo, idx))
            stack.append((idx, hi))
    return [c for c, k in zip(coords, keep) if k]


def resample_polyline(coords: list[Point], step_m: float) -> list[Point]:
    """Rotayı ~eşit aralıklı noktalara böler. Güneş konumunu segment boyunca
    ilerletirken çözünürlüğü sabit tutar; açı hesabını da dengeler."""
    if len(coords) < 2 or step_m <= 0:
        return list(coords)

    out: list[Point] = [coords[0]]
    carry = 0.0  # bir sonraki çıktı noktasına kalan mesafe borcu
    for a, b in zip(coords, coords[1:]):
        seg = haversine_m(a, b)
        if seg < 1e-9:
            continue
        d = step_m - carry
        while d < seg:
            f = d / seg
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            d += step_m
        carry = seg - (d - step_m)
    if out[-1] != coords[-1]:
        out.append(coords[-1])
    return out


def smooth_route(
    coords: list[Point],
    *,
    simplify_epsilon_m: float = 25.0,
    resample_step_m: float | None = 40.0,
) -> list[Point]:
    """Ham güzergah polyline'ını analiz için temizler: önce RDP (titreme /
    rotari gürültüsü), sonra eşit aralıklı yeniden örnekleme."""
    out = rdp_simplify(coords, simplify_epsilon_m)
    if resample_step_m:
        out = resample_polyline(out, resample_step_m)
    return out


def point_in_zones(p: Point, zones: list[tuple[float, float, float]]) -> bool:
    """zones: (lat, lon, yarıçap_m) daireleri. p herhangi birinin içinde mi?"""
    return any(haversine_m(p, (zlat, zlon)) <= radius for zlat, zlon, radius in zones)
