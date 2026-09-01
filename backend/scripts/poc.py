"""Gölge Rota — çekirdek algoritma PoC'si.

Burulaş'a hiç dokunmadan, statik GeoJSON rotalar üzerinde güneş-tarafı
hesabını gösterir.

Kullanım:
    python -m scripts.poc                         # tüm rotalar, "şimdi"
    python -m scripts.poc bursaray-t1 2026-09-01T18:30
    python -m scripts.poc bus-38 2026-06-21T08:00 backward
"""
from __future__ import annotations

import sys
from datetime import datetime

# Windows konsolu cp1254 olabilir; Türkçe/ok karakterleri için UTF-8'e geç.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from app.core.shadow import Side, analyze
from app.core.sun import TURKEY_TZ, get_sun
from app.routes_repo import load_routes

BAR = {Side.LEFT: "<< SOL ", Side.RIGHT: " SAG >>", Side.FRONT: "^^ ON  ",
       Side.BACK: "vv ARKA", Side.NONE: "  --   "}


def run(route_id: str, departure: datetime, direction: str) -> None:
    route = load_routes()[route_id]
    coords, tunnels = route.path(direction)
    res = analyze(coords, departure, avg_speed_kmh=route.avg_speed_kmh, tunnel_segments=tunnels)

    print("=" * 78)
    print(f"{route.name}   [{route.direction_labels.get(direction, direction)}]")
    print(f"Kalkış: {departure:%Y-%m-%d %H:%M} (+03)   "
          f"Süre ~{res.trip_duration_min:.0f} dk   Uzunluk {res.total_length_m/1000:.1f} km")
    print("-" * 78)
    print(f"{'#':>2}  {'yön°':>5}  {'saat':>5}  {'g.azimut':>8}  {'g.yük':>6}  taraf")
    for s in res.segments:
        t = s.when.strftime("%H:%M")
        print(f"{s.index:>2}  {s.bearing_deg:>5.0f}  {t:>5}  {s.sun_azimuth_deg:>8.0f}  "
              f"{s.sun_altitude_deg:>6.1f}  {BAR[s.side]}"
              f"{'  (tünel)' if s.in_tunnel else ''}")
    print("-" * 78)
    for side in (Side.LEFT, Side.RIGHT, Side.FRONT, Side.BACK, Side.NONE):
        print(f"  {side.tr:>4}: %{res.pct_length(side):>4.0f} rota   "
              f"(ağırlıklı maruz kalma {res.exposure_by_side.get(side, 0.0):>6.1f})")
    print("-" * 78)
    print(f"  >>> {res.headline}")
    for n in res.notes:
        print(f"      - {n}")
    print()


def main(argv: list[str]) -> None:
    routes = load_routes()
    route_ids = [argv[0]] if argv and argv[0] in routes else list(routes)
    when_arg = next((a for a in argv if a[:4].isdigit()), None)
    direction = "backward" if "backward" in argv else "forward"

    departure = (
        datetime.fromisoformat(when_arg).replace(tzinfo=TURKEY_TZ)
        if when_arg else datetime.now(TURKEY_TZ)
    )

    # Küçük akıl sağlığı kontrolü: Bursa'da güneş şu an nerede?
    sp = get_sun(departure, 40.19, 29.06)
    print(f"\nBursa @ {departure:%Y-%m-%d %H:%M} +03  ->  "
          f"güneş azimut {sp.azimuth_deg:.0f}°, yükseklik {sp.altitude_deg:.0f}°\n")

    for rid in route_ids:
        run(rid, departure, direction)


if __name__ == "__main__":
    main(sys.argv[1:])
