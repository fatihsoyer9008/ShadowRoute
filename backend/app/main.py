"""Gölge Rota — ince backend (FastAPI).

Sorumluluk: statik/ileride Burulaş kaynaklı rota verisini sunmak ve güneş-tarafı
analizini çalıştırmak. Ağır iş `app.core` içinde; burası sadece HTTP kabuğu.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .core.shadow import analyze
from .core.sun import TURKEY_TZ
from .routes_repo import load_routes

app = FastAPI(title="Gölge Rota API", version="0.1.0")

# Geliştirme kolaylığı: Flutter web / farklı port'tan erişime izin ver.
# Prod'da bunu gerçek origin listesiyle daralt.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

ROUTES = load_routes()


@app.get("/routes")
def list_routes():
    return [
        {
            "id": r.id,
            "name": r.name,
            "mode": r.mode,
            "directions": r.direction_labels,
            "stops": r.stops,
        }
        for r in ROUTES.values()
    ]


@app.get("/routes/{route_id}/shadow")
def route_shadow(
    route_id: str,
    direction: str = Query("forward", pattern="^(forward|backward)$"),
    when: datetime | None = Query(
        None, description="ISO 8601 kalkış zamanı. Boşsa: Türkiye saatiyle şimdi."
    ),
):
    route = ROUTES.get(route_id)
    if route is None:
        raise HTTPException(404, f"Bilinmeyen rota: {route_id}")

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
        "direction": direction,
        "direction_label": route.direction_labels.get(direction, direction),
    }
    return payload
