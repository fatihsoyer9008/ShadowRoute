"""Statik GeoJSON güzergahlarını yükler (MVP'de veritabanı yok).

Burulaş API entegrasyonu geldiğinde bu modülün arkasına bir 'canlı' kaynak
eklenir; çağıranlar aynı `Route` arayüzünü görmeye devam eder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import burulas
from .core.geo import Point, auto_loop_split, haversine_m

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
    tunnel_zones: list[TunnelZone]   # coğrafi; yöne bağlı değil
    coords: list[Point]             # (lat, lon), gidiş yönü / halka tur sırası
    stops: list[str]
    stop_points: list[Point] = field(default_factory=list)  # `stops` ile paralel
    loop_split: int | None = None   # kapalı halka hatlarda dönüş noktasının indeksi
    hat_no: int | None = None       # Burulaş hatNo (varsa) — canlı fallback için

    @property
    def is_loop(self) -> bool:
        return self.loop_split is not None or (
            len(self.coords) > 3
            and haversine_m(self.coords[0], self.coords[-1]) < 350
        )

    def canonical_stops(self) -> list[tuple[str, int]]:
        """(durak adı, en yakın `coords` noktası indeksi) — yolculuk sırasıyla.
        Düz hatta gidiş yönü; halka hatta bütün tur. `stop_points` yoksa boş."""
        if not self.stop_points:
            return []
        n = len(self.coords)
        out: list[tuple[str, int]] = []
        for name, p in zip(self.stops, self.stop_points):
            i = min(range(n), key=lambda k: haversine_m(self.coords[k], p))
            out.append((name, i))
        out.sort(key=lambda t: t[1])
        return out

    def default_span(self) -> tuple[int, int]:
        """from/to verilmezse analiz edilecek durak aralığı (canonical index).
        Düz hat: tüm hat. Halka: başlangıç → dönüş noktası (ilk yarım tur)."""
        stops = self.canonical_stops()
        if len(stops) < 2:
            return (0, 0)
        if self.loop_split is not None:
            turn = min(range(len(stops)),
                       key=lambda k: abs(stops[k][1] - self.loop_split))
            if turn >= 1:
                return (0, turn)
        return (0, len(stops) - 1)

    def slice_between(
        self, from_i: int, to_i: int
    ) -> tuple[list[Point], list[TunnelZone]]:
        """from_i/to_i: `canonical_stops()` içindeki durak sıraları.
        from < to → düz git; from > to → düz hatta ters yön, halka hatta turu
        tamamla. Tünel bölgeleri coğrafi, yönden bağımsız."""
        stops = self.canonical_stops()
        if not (0 <= from_i < len(stops)) or not (0 <= to_i < len(stops)):
            raise ValueError("Durak sırası aralık dışında")
        if from_i == to_i:
            raise ValueError("Biniş ve iniş durağı aynı olamaz")

        a, b = stops[from_i][1], stops[to_i][1]
        if a < b:
            coords = self.coords[a : b + 1]
        elif self.is_loop:
            coords = self.coords[a:] + self.coords[: b + 1]      # turu tamamla
        else:
            coords = list(reversed(self.coords[b : a + 1]))       # ters yön
        if len(coords) < 2:
            raise ValueError("Seçilen durak aralığı çok kısa")
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
        tunnel_zones=zones,
        coords=coords,
        stops=props.get("stops", []),
        stop_points=[(lat, lon) for lon, lat in props.get("stop_coords", [])],
        loop_split=props.get("loop_split"),
        hat_no=props.get("hat_no"),
    )


def load_routes() -> dict[str, Route]:
    shared = _load_shared_zones()
    return {
        r.id: r
        for r in (_load_one(fp, shared) for fp in sorted(ROUTES_DIR.glob("*.geojson")))
    }


def static_by_hat_no() -> dict[int, Route]:
    """hatNo -> elle bakımı yapılan Route (varsa)."""
    return {r.hat_no: r for r in load_routes().values() if r.hat_no is not None}


# --- Burulaş'tan canlı çekilen rotalar (arama sonucu seçilenler) ----------
LIVE_PREFIX = "live-"


def live_route(hat_no: int) -> Route:
    """Burulaş API'sinden bir hattı `Route` olarak kurar.

    Elle bakım yok: tünel bölgesi yok, halka ise dönüş noktası otomatik
    tahmin edilir (`auto_loop_split`). Sonuçlar `burulas` katmanında (bellek +
    disk) cache'li. Bu hatNo için elle ayarlı bir hat varsa (tünel bölgeleri,
    isim) o tercih edilir — Burulaş erişilemezse de bu devreye girer.
    """
    curated = static_by_hat_no().get(hat_no)
    if curated is not None:
        return curated

    meta = burulas.line_meta(hat_no) or {
        "code": str(hat_no), "name": str(hat_no), "mode": "bus"
    }

    coords = burulas.directional_paths(hat_no)["forward"]
    stop_rows = burulas.stops_with_coords(hat_no)

    return Route(
        id=f"{LIVE_PREFIX}{hat_no}",
        name=f"{meta['code']} — {meta['name']}" if meta["name"] != meta["code"] else meta["code"],
        mode=meta["mode"],
        avg_speed_kmh=33.0 if meta["mode"] == "metro" else 20.0,
        tunnel_zones=[],
        coords=coords,
        stops=[n for n, _ in stop_rows],
        stop_points=[p for _, p in stop_rows],
        loop_split=auto_loop_split(coords),
    )
    parts = []
    for w in n.split():
        if "." in w or any(c.isdigit() for c in w):
            continue
        parts.append(w[0].upper().replace("I", "İ")
                     + w[1:].replace("I", "ı").replace("İ", "i").lower())
    return " ".join(parts[:max_words]) or stop_name.title()
