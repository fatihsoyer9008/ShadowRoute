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
    return {
        "id": r.id,
        "name": r.name,
        "mode": r.mode,
        "directions": r.direction_labels,
        "is_loop": r.loop_split is not None,
        "stops": r.stops,
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
    direction: str = Query("forward", pattern="^(forward|backward)$"),
    when: datetime | None = Query(
        None, description="ISO 8601 kalkış zamanı. Boşsa: Türkiye saatiyle şimdi."
    ),
):
    route = _resolve(route_id)

    departure = when or datetime.now(TURKEY_TZ)
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=TURKEY_TZ)

    coords, tunnel_zones = route.path(direction)
    result = analyze(
        coords,
        departure,
        avg_speed_kmh=route.avg_speed_kmh,
        tunnel_zones=tunnel_zones,
    )

    payload = result.to_dict()
    payload["route"] = {
        "id": route.id,
        "name": route.name,
        "mode": route.mode,
        "is_loop": route.loop_split is not None,
        "curated": route.id in STATIC_ROUTES,
        "direction": direction,
        "direction_label": route.direction_labels.get(direction, direction),
    }
    return payload
