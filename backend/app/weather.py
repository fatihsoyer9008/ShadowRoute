"""OpenWeather — rota orta noktası için anlık bulutluluk.

Amaç güneş önerisini EZMEK değil, bağlam vermek: "hava %75 bulutlu, ama güneş
açarsa sağ taraf riskli". Sorumluluk kullanıcıda kalır.

`OPENWEATHER_API_KEY` env değişkeni yoksa modül sessizce devre dışı — analiz
etkilenmez. Sonuçlar koordinat başına 15 dk cache'li.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()
_URL = "https://api.openweathermap.org/data/2.5/weather"
_TIMEOUT = 6
_TTL_S = 900

_CACHE: dict[tuple[float, float], tuple[float, dict]] = {}


def enabled() -> bool:
    return bool(_KEY)


def current(lat: float, lon: float) -> dict | None:
    """{'clouds_pct', 'condition', 'description', 'temp_c'} ya da None."""
    if not _KEY:
        return None

    key = (round(lat, 2), round(lon, 2))
    now = time.time()
    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < _TTL_S:
        return hit[1]

    q = urllib.parse.urlencode({
        "lat": f"{lat:.4f}", "lon": f"{lon:.4f}",
        "appid": _KEY, "units": "metric", "lang": "tr",
    })
    try:
        with urllib.request.urlopen(f"{_URL}?{q}", timeout=_TIMEOUT) as resp:
            raw: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None

    w0 = (raw.get("weather") or [{}])[0]
    out = {
        "clouds_pct": int(raw.get("clouds", {}).get("all", 0)),
        "condition": str(w0.get("main", "")),
        "description": str(w0.get("description", "")),
        "temp_c": round(float(raw.get("main", {}).get("temp", 0.0))),
    }
    _CACHE[key] = (now, out)
    return out
