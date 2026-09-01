"""Statik GeoJSON güzergahlarını yükler (MVP'de veritabanı yok).

Burulaş API entegrasyonu geldiğinde bu modülün arkasına bir 'canlı' kaynak
eklenir; çağıranlar aynı `Route` arayüzünü görmeye devam eder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .core.geo import Point

DATA_DIR = Path(__file__).parent / "data"
ROUTES_DIR = DATA_DIR / "routes"
SHARED_ZONES_FILE = DATA_DIR / "tunnel_zones.json"


TunnelZone = tuple[float, float, float]  # (lat, lon, yarıçap_m)


def _load_shared_zones() -> dict[str, list[TunnelZone]]:
    """M1/M2 ortak yeraltı bölgeleri (bkz. data/tunnel_zones.json)."""
    if not SHARED_ZONES_FILE.exists():
        return {}
    raw = json.loads(SHARED_ZONES_FILE.read_text(encoding="utf-8"))
    return {
        key: [tuple(z) for z in group["zones"]]
        for key, group in raw.items()
        if isinstance(group, dict) and "zones" in group
    }


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


def _load_one(fp: Path, shared_zones: dict[str, list[TunnelZone]]) -> Route:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    props = raw["properties"]
    lonlat = raw["geometry"]["coordinates"]
    coords: list[Point] = [(lat, lon) for lon, lat in lonlat]

    zones: list[TunnelZone] = [tuple(z) for z in props.get("tunnel_zones", [])]
    for ref in props.get("tunnel_zone_refs", []):
        if ref not in shared_zones:
            raise KeyError(f"{fp.name}: bilinmeyen tunnel_zone_refs '{ref}'")
        zones.extend(shared_zones[ref])

    return Route(
        id=props["id"],
        name=props["name"],
        mode=props.get("mode", "bus"),
        avg_speed_kmh=float(props.get("avg_speed_kmh", 18)),
        direction_labels=props.get(
            "direction_labels", {"forward": "Gidiş", "backward": "Dönüş"}
        ),
        tunnel_zones=zones,
        coords=coords,
        stops=props.get("stops", []),
    )


def load_routes() -> dict[str, Route]:
    shared = _load_shared_zones()
    return {
        r.id: r
        for r in (_load_one(fp, shared) for fp in sorted(ROUTES_DIR.glob("*.geojson")))
    }
