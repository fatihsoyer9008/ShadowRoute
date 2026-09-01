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
    direction_labels: dict[str, str]
    tunnel_zones: list[TunnelZone]   # coğrafi; yöne bağlı değil
    coords: list[Point]             # (lat, lon), forward yön
    stops: list[str]
    stop_points: list[Point] = field(default_factory=list)  # `stops` ile paralel
    loop_split: int | None = None   # kapalı halka hatlarda dönüş noktasının indeksi
    hat_no: int | None = None       # Burulaş hatNo (varsa) — canlı fallback için

    def _dir_coords(self, direction: str) -> list[Point]:
        if self.loop_split is not None:
            s = self.loop_split
            return self.coords[: s + 1] if direction == "forward" else self.coords[s:]
        return self.coords if direction == "forward" else list(reversed(self.coords))

    def stops_for(self, direction: str) -> list[tuple[str, int]]:
        """O yöndeki duraklar: (isim, o yönün coords listesindeki en yakın indeks).
        Sıralı. stop_points yoksa boş liste."""
        if not self.stop_points:
            return []
        dc = self._dir_coords(direction)
        n = len(self.coords)

        def to_dir_index(fwd_i: int) -> int | None:
            if self.loop_split is None:
                return fwd_i if direction == "forward" else (n - 1 - fwd_i)
            s = self.loop_split
            if direction == "forward":
                return fwd_i if fwd_i <= s else None
            return (fwd_i - s) if fwd_i >= s else None

        out: list[tuple[str, int]] = []
        for name, p in zip(self.stops, self.stop_points):
            fwd_i = min(range(n), key=lambda i: haversine_m(self.coords[i], p))
            di = to_dir_index(fwd_i)
            if di is not None and 0 <= di < len(dc):
                out.append((name, di))
        out.sort(key=lambda t: t[1])
        return out

    def path(
        self, direction: str, start_i: int | None = None, end_i: int | None = None
    ) -> tuple[list[Point], list[TunnelZone]]:
        """direction: 'forward' | 'backward'. start_i/end_i verilirse o yönün
        coords listesi bu indeksler arasına daraltılır (duraktan durağa).

        Düz hat: backward = koordinatların tersi. Halka hat (`loop_split`):
        forward = başlangıç→dönüş, backward = dönüş→başlangıç. Tünel bölgeleri
        coğrafi, yönden bağımsız."""
        if direction not in ("forward", "backward"):
            raise ValueError("direction 'forward' ya da 'backward' olmalı")
        coords = self._dir_coords(direction)
        if start_i is not None or end_i is not None:
            a = max(0, start_i or 0)
            b = min(len(coords), (end_i if end_i is not None else len(coords) - 1) + 1)
            if b - a < 2:
                raise ValueError("Seçilen durak aralığı çok kısa")
            coords = coords[a:b]
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

    paths = burulas.directional_paths(hat_no)
    coords = paths["forward"]
    stop_rows = burulas.stops_with_coords(hat_no)
    stops = [n for n, _ in stop_rows]
    stop_points = [p for _, p in stop_rows]

    split = auto_loop_split(coords)
    if not stops:
        labels = {"forward": "Gidiş", "backward": "Dönüş"}
    elif split is not None:
        turn_i = round(split / max(len(coords) - 1, 1) * (len(stops) - 1))
        turn_i = min(len(stops) - 1, max(0, turn_i))
        labels = {"forward": f"{_short(stops[turn_i])} yönü",
                  "backward": f"{_short(stops[0])} yönü"}
    else:
        labels = {"forward": f"{_short(stops[-1])} yönü",
                  "backward": f"{_short(stops[0])} yönü"}

    return Route(
        id=f"{LIVE_PREFIX}{hat_no}",
        name=f"{meta['code']} — {meta['name']}" if meta["name"] != meta["code"] else meta["code"],
        mode=meta["mode"],
        avg_speed_kmh=33.0 if meta["mode"] == "metro" else 20.0,
        direction_labels=labels,
        tunnel_zones=[],
        coords=coords,
        stops=stops,
        stop_points=stop_points,
        loop_split=split,
    )


def _short(stop_name: str, max_words: int = 2) -> str:
    """"HEYKEL ATATÜRK CD. PERON 1" -> "Heykel Atatürk" gibi kısalt."""
    import re

    n = re.sub(r"\s*\([^)]*\)\s*$", "", stop_name.strip())
    n = re.sub(r"\s+(PERON\s*)?\d+$", "", n)
    n = re.sub(r"\b(CD|CAD|MH|MAH|BLV|SK|SOK|İST|İSTASYONU|PERON)\.?\b", "", n, flags=re.I)
    parts = []
    for w in n.split():
        if "." in w or any(c.isdigit() for c in w):
            continue
        parts.append(w[0].upper().replace("I", "İ")
                     + w[1:].replace("I", "ı").replace("İ", "i").lower())
    return " ".join(parts[:max_words]) or stop_name.title()
