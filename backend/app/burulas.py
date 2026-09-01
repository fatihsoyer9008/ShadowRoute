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

import hashlib
import json
import ssl
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .core.geo import Point

BASE_URL = "https://bursakartapi.abys-web.com"
CACHE_DIR = Path(__file__).parent / "data" / ".cache"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.bursakart.com.tr",
    "User-Agent": "GolgeRota/0.1 (+https://github.com/)",
}
_TIMEOUT = 20


class BurulasError(RuntimeError):
    pass


# --- TTL cache: bellek + disk (rotalar nadiren değişir) -------------------
# Disk katmanı sayesinde sunucu yeniden başlasa da cache'lenmiş hatlar
# (ve Burulaş erişilemezse) yeniden çekmeye gerek kalmadan kullanılabilir.
_CACHE: dict[tuple, tuple[float, Any]] = {}


def _disk_path(key: tuple) -> Path:
    h = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{key[0]}-{h}.json"


def _cached(key: tuple, ttl_s: float, produce: Callable[[], Any]) -> Any:
    now = time.time()

    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < ttl_s:
        return hit[1]

    fp = _disk_path(key)
    disk = None
    if fp.exists():
        try:
            disk = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            disk = None
    if disk is not None and now - disk["ts"] < ttl_s:
        _CACHE[key] = (disk["ts"], disk["value"])
        return disk["value"]

    try:
        value = produce()
    except BurulasError:
        # Burulaş down -> bayat da olsa diskteki veriyi ver.
        if disk is not None:
            _CACHE[key] = (disk["ts"], disk["value"])
            return disk["value"]
        raise

    _CACHE[key] = (now, value)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps({"ts": now, "value": value}, ensure_ascii=False),
                      encoding="utf-8")
    except OSError:
        pass
    return value


# hatNo -> {'code','name','mode'} — aramalar sırasında dolar; `live_route`
# sadece hatNo bildiği için buradan hattın kodunu/adını çeker.
_LINE_META: dict[int, dict] = {}


def clear_cache() -> None:
    _CACHE.clear()


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
    """type='R' -> hat, type='S' -> durak. 1 saat cache."""
    kw = str(keyword).strip()
    return _cached(("search", kw.lower()), 3600.0,
                   lambda: _post("api/static/routeandstation", {"keyword": kw}))


def route_coordinates(route_id: int | str) -> list[dict]:
    return _cached(("coord", str(route_id)), 12 * 3600.0,
                   lambda: _post("api/static/routecoordinate", {"keyword": str(route_id)}))


def route_stops(route_code: int | str) -> list[dict]:
    return _cached(("stops", int(route_code)), 12 * 3600.0,
                   lambda: _post("api/static/routestat", {"routeCode": int(route_code)}))


def search_lines(keyword: str) -> list[dict]:
    """Arama sonucundan yalnız hatları normalize eder:
    [{'hat_no': 1012, 'code': '38', 'name': '38', 'mode': 'bus'}, ...]"""
    out = []
    for r in search(keyword):
        if r.get("type") != "R" or "hatNo" not in r:
            continue
        code = str(r.get("kod", r["hatNo"]))
        mode = "metro" if code[:1].upper() in ("M", "T") else "bus"
        meta = {"hat_no": int(r["hatNo"]), "code": code,
                "name": str(r.get("aciklama") or code), "mode": mode}
        _LINE_META[meta["hat_no"]] = {k: meta[k] for k in ("code", "name", "mode")}
        out.append(meta)
    return out


def line_meta(hat_no: int) -> dict | None:
    """Daha önce bir aramada görülen hattın kodu/adı/modu. Görülmediyse None."""
    return _LINE_META.get(int(hat_no))


def find_route(code: str) -> dict:
    """'38' -> {'kod': '38', 'hatNo': 1012, ...}. Tam eşleşme, yoksa ilk 'R'."""
    hits = [r for r in search(code) if r.get("type") == "R"]
    if not hits:
        raise BurulasError(f"'{code}' için hat bulunamadı")
    exact = [r for r in hits if str(r.get("kod", "")).lower() == code.lower()]
    return exact[0] if exact else hits[0]


def stops_with_coords(
    route_code: int | str, direction: str = "G"
) -> list[tuple[str, Point]]:
    """[(durak adı, (lat, lon)), ...] sıralı. Bitişik birebir tekrarlar atılır."""
    rows = [s for s in route_stops(route_code) if s.get("direction") in (direction, "R")]
    rows.sort(key=lambda s: int(s["sequence"]))
    out: list[tuple[str, Point]] = []
    for s in rows:
        nm = str(s.get("stopName", "")).strip()
        try:
            p = (float(s["latitude"]), float(s["longitude"]))
        except (KeyError, TypeError, ValueError):
            continue
        if nm and (not out or out[-1][0] != nm):
            out.append((nm, p))
    return out


def stop_names(route_code: int | str, direction: str = "G") -> list[str]:
    return [n for n, _ in stops_with_coords(route_code, direction)]


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
