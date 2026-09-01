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


TunnelZone = tuple[float, float, float]  # (lat, lon, yarıçap_m)


@dataclass(frozen=True)
class Route:
    id: str
    name: str
    mode: str                       # "bus" | "metro"
    avg_speed_kmh: float
    direction_labels: dict[str, str]
    tunnel_zones: list[TunnelZone]   # coğrafi; yöne bağlı değil
    coords: list[Point]             # (lat, lon), forward yön
    stops: list[str]

    def path(self, direction: str) -> tuple[list[Point], list[TunnelZone]]:
        """direction: 'forward' | 'backward'. Tünel bölgeleri coğrafi olduğu
        için yönle değişmez; sadece koordinatlar ters çevrilir."""
        if direction not in ("forward", "backward"):
            raise ValueError("direction 'forward' ya da 'backward' olmalı")
        coords = self.coords if direction == "forward" else list(reversed(self.coords))
        return coords, self.tunnel_zones


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
        tunnel_zones=[tuple(z) for z in props.get("tunnel_zones", [])],
        coords=coords,
        stops=props.get("stops", []),
    )


def load_routes() -> dict[str, Route]:
    return {r.id: r for r in (_load_one(fp) for fp in sorted(ROUTES_DIR.glob("*.geojson")))}
