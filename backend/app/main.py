"""Gölge Rota — ince backend (FastAPI).

Sorumluluk: statik + Burulaş kaynaklı rota verisini sunmak ve güneş-tarafı
analizini çalıştırmak. Ağır iş `app.core` içinde; burası sadece HTTP kabuğu.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import burulas
from .core.shadow import analyze
from .core.sun import TURKEY_TZ
from .routes_repo import LIVE_PREFIX, Route, live_route, load_routes

app = FastAPI(title="Gölge Rota API", version="0.2.0")

# Geliştirme kolaylığı: Flutter web / farklı port'tan erişime izin ver.
# Prod'da bunu gerçek origin listesiyle daralt.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

STATIC_ROUTES = load_routes()


def _resolve(route_id: str) -> Route:
    """Statik id ('bursaray-m1') ya da canlı id ('live-1012') -> Route."""
    if route_id in STATIC_ROUTES:
        return STATIC_ROUTES[route_id]
    if route_id.startswith(LIVE_PREFIX):
        try:
            return live_route(int(route_id[len(LIVE_PREFIX):]))
        except (ValueError, burulas.BurulasError) as e:
            raise HTTPException(502, f"Burulaş'tan rota alınamadı: {e}") from e
    raise HTTPException(404, f"Bilinmeyen rota: {route_id}")


def _summary(r: Route) -> dict:
    stops = [name for name, _ in r.canonical_stops()]
    lo, hi = r.default_span()
    return {
        "id": r.id,
        "name": r.name,
        "mode": r.mode,
        "is_loop": r.is_loop,
        # Yolculuk sırasıyla duraklar. Kullanıcı buradan biniş/iniş seçer;
        # yön, seçilen durak sırasından çıkar (ayrı "yön" seçimi yok).
        "stops": stops or r.stops,
        "default_from": lo,
        "default_to": hi,
    }


@app.get("/routes")
def list_routes():
    """Elle bakımı yapılan, tünel bölgeleri ayarlı hatlar."""
    return [_summary(r) for r in STATIC_ROUTES.values()]


def _curated_matches(q: str) -> list[dict]:
    ql = q.strip().lower()
    hits = []
    for r in STATIC_ROUTES.values():
        if ql in r.name.lower() or (r.hat_no and ql == str(r.hat_no)):
            hits.append({"id": r.id, "code": r.name.split(" ")[0],
                         "name": r.name, "mode": r.mode})
    return hits


@app.get("/search")
def search_lines(q: str = Query(..., min_length=1, description="Hat kodu ya da adı")):
    """Burulaş'ta hat arar. Sonuç id'leri 'live-<hatNo>' — /routes/{id}/shadow
    ile doğrudan kullanılabilir (tünel bölgesi yok, halka ise otomatik bölünür).
    Burulaş erişilemezse elle bakımı yapılan hatlar arasında arar."""
    try:
        lines = burulas.search_lines(q)
    except burulas.BurulasError:
        return _curated_matches(q)
    return [
        {"id": f"{LIVE_PREFIX}{l['hat_no']}", "code": l["code"],
         "name": l["name"], "mode": l["mode"]}
        for l in lines
    ]


@app.get("/routes/{route_id}")
def route_detail(route_id: str):
    return _summary(_resolve(route_id))


@app.get("/routes/{route_id}/shadow")
def route_shadow(
    route_id: str,
    when: datetime | None = Query(
        None, description="ISO 8601 kalkış zamanı. Boşsa: Türkiye saatiyle şimdi."
    ),
    from_stop: int | None = Query(
        None, alias="from", ge=0, description="Biniş durağı sırası (0-tabanlı)"
    ),
    to_stop: int | None = Query(
        None, alias="to", ge=0, description="İniş durağı sırası (0-tabanlı)"
    ),
):
    route = _resolve(route_id)

    departure = when or datetime.now(TURKEY_TZ)
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=TURKEY_TZ)

    stops = route.canonical_stops()
    lo, hi = route.default_span()
    if from_stop is not None:
        lo = from_stop
    if to_stop is not None:
        hi = to_stop

    from_name = to_name = None
    try:
        if stops:
            coords, tunnel_zones = route.slice_between(lo, hi)
            from_name, to_name = stops[lo][0], stops[hi][0]
        else:  # durak verisi yok -> tüm güzergah
            coords, tunnel_zones = route.coords, route.tunnel_zones
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    result = analyze(
        coords, departure,
        avg_speed_kmh=route.avg_speed_kmh, tunnel_zones=tunnel_zones,
    )

    payload = result.to_dict()
    payload["route"] = {
        "id": route.id,
        "name": route.name,
        "mode": route.mode,
        "is_loop": route.is_loop,
        "curated": route.id in STATIC_ROUTES,
        "from_stop": from_name,
        "to_stop": to_name,
    }
    return payload
