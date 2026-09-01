"""Burulaş / BursaKart (ABYS) API istemcisi.

Resmi dokümante bir API değil; `erenbozaci/fetchingburulasapi` reverse-engineer
çalışmasından çıkarıldı. Kimlik doğrulama yok, POST + JSON gövde.

Sözleşme kırılgandır -> her zaman `routes_repo` içindeki statik GeoJSON'a
düşebilmeliyiz (bkz. plan.md Faz 0 / Plan B).

Endpoint'ler:
  POST /api/static/routeandstation   {"keyword": "38"}        -> hat + durak arama
  POST /api/static/routecoordinate   {"keyword": "1012"}      -> güzergah polyline
  POST /api/static/routestat         {"routeCode": 1012}      -> sıralı duraklar

Notlar:
  - `routecoordinate` cevabında alan adı "logitude" (API tarafında typo).
  - `routeDirection`: "G" = gidiş, "D" = dönüş, "R" = tek yön verilmiş.
  - Bazı hatlarda tek yön (R) döner; diğer yönü biz ters çeviririz.
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from typing import Any

from .core.geo import Point

BASE_URL = "https://bursakartapi.abys-web.com"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.bursakart.com.tr",
    "User-Agent": "GolgeRota/0.1 (+https://github.com/)",
}
_TIMEOUT = 20


class BurulasError(RuntimeError):
    pass


def _post(path: str, body: dict[str, Any]) -> list[dict]:
    req = urllib.request.Request(
        f"{BASE_URL}/{path.lstrip('/')}",
        data=json.dumps(body).encode("utf-8"),
        headers=_HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:  # ağ / TLS / DNS
        raise BurulasError(f"{path}: istek başarısız ({e})") from e
    if "result" not in payload:
        raise BurulasError(f"{path}: beklenmeyen cevap {payload!r:.200}")
    return payload["result"]


# Bazı ortamlarda ABYS zinciri doğrulanamıyor; referans kod da cert kontrolünü
# kapatıyordu. İhtiyaç olursa (yalnızca bu host için) elle çağrılabilir.
def _insecure_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def search(keyword: str) -> list[dict]:
    """type='R' -> hat, type='S' -> durak."""
    return _post("api/static/routeandstation", {"keyword": str(keyword)})


def route_coordinates(route_id: int | str) -> list[dict]:
    return _post("api/static/routecoordinate", {"keyword": str(route_id)})


def route_stops(route_code: int | str) -> list[dict]:
    return _post("api/static/routestat", {"routeCode": int(route_code)})


def find_route(code: str) -> dict:
    """'38' -> {'kod': '38', 'hatNo': 1012, ...}. Tam eşleşme, yoksa ilk 'R'."""
    hits = [r for r in search(code) if r.get("type") == "R"]
    if not hits:
        raise BurulasError(f"'{code}' için hat bulunamadı")
    exact = [r for r in hits if str(r.get("kod", "")).lower() == code.lower()]
    return exact[0] if exact else hits[0]


def _coord(p: dict) -> Point:
    # (lat, lon); API alan adı "logitude"
    return (float(p["latitude"]), float(p.get("logitude", p.get("longitude"))))


def directional_paths(route_id: int | str) -> dict[str, list[Point]]:
    """{'forward': [...], 'backward': [...]} döner.

    routeDirection 'G'/'R' -> forward, 'D' -> backward. 'D' yoksa forward'ın
    tersi kullanılır.
    """
    raw = route_coordinates(route_id)
    fwd = sorted((p for p in raw if p.get("routeDirection") in ("G", "R")),
                 key=lambda p: int(p["sequence"]))
    bwd = sorted((p for p in raw if p.get("routeDirection") == "D"),
                 key=lambda p: int(p["sequence"]))
    forward = [_coord(p) for p in fwd] or [_coord(p) for p in
              sorted(raw, key=lambda p: int(p["sequence"]))]
    backward = [_coord(p) for p in bwd] or list(reversed(forward))
    return {"forward": forward, "backward": backward}
