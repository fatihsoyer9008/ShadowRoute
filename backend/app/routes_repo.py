"""Statik GeoJSON güzergahlarını yükler (MVP'de veritabanı yok).

Burulaş API entegrasyonu geldiğinde bu modülün arkasına bir 'canlı' kaynak
eklenir; çağıranlar aynı `Route` arayüzünü görmeye devam eder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .core.geo import Point

ROUTES_DIR = Path(__file__).parent / "data" / "routes"


@dataclass(frozen=True)
class Route:
    id: str
    name: str
    mode: str                       # "bus" | "metro"
    avg_speed_kmh: float
    direction_labels: dict[str, str]
    tunnel_segments: list[tuple[int, int]]
    coords: list[Point]             # (lat, lon), forward yön
    stops: list[str]

    def path(self, direction: str) -> tuple[list[Point], list[tuple[int, int]]]:
        """direction: 'forward' | 'backward'. Backward'da koordinatları ve
        tünel indekslerini ters çevirir."""
        if direction not in ("forward", "backward"):
            raise ValueError("direction 'forward' ya da 'backward' olmalı")
        if direction == "forward":
            return self.coords, self.tunnel_segments
        rev = list(reversed(self.coords))
        n_seg = len(self.coords) - 1
        # forward segment i (nokta i->i+1), backward'da segment (n_seg-1-i)
        rev_tun = [(n_seg - 1 - hi, n_seg - 1 - lo) for lo, hi in self.tunnel_segments]
        return rev, rev_tun


def _load_one(fp: Path) -> Route:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    props = raw["properties"]
    lonlat = raw["geometry"]["coordinates"]
    coords: list[Point] = [(lat, lon) for lon, lat in lonlat]
    return Route(
        id=props["id"],
        name=props["name"],
        mode=props.get("mode", "bus"),
        avg_speed_kmh=float(props.get("avg_speed_kmh", 18)),
        direction_labels=props.get(
            "direction_labels", {"forward": "Gidiş", "backward": "Dönüş"}
        ),
        tunnel_segments=[tuple(x) for x in props.get("tunnel_segments", [])],
        coords=coords,
        stops=props.get("stops", []),
    )


def load_routes() -> dict[str, Route]:
    return {r.id: r for r in (_load_one(fp) for fp in sorted(ROUTES_DIR.glob("*.geojson")))}
