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
