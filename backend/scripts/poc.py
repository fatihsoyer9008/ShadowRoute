"""Gölge Rota — çekirdek algoritma PoC'si.

Burulaş'a hiç dokunmadan, statik GeoJSON rotalar üzerinde güneş-tarafı
hesabını gösterir.

Kullanım:
    python -m scripts.poc                         # tüm rotalar, "şimdi"
    python -m scripts.poc bursaray-m1 2026-09-01T18:30
    python -m scripts.poc bursaray-m1 2026-06-21T08:00 10:15   # 11.->16. durak arası
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


def run(route_id: str, departure: datetime, span: tuple[int, int] | None) -> None:
    route = load_routes()[route_id]
    stops = route.canonical_stops()
    lo, hi = span or route.default_span()
    label = f"{route.name}"
    if stops:
        coords, tunnel_zones = route.slice_between(lo, hi)
        label += f"   [{stops[lo][0]} → {stops[hi][0]}]"
    else:
        coords, tunnel_zones = route.coords, route.tunnel_zones
    res = analyze(coords, departure, avg_speed_kmh=route.avg_speed_kmh,
                  tunnel_zones=tunnel_zones)

    print("=" * 78)
    print(label)
    print(f"Kalkış: {departure:%Y-%m-%d %H:%M} (+03)   "
          f"Süre ~{res.trip_duration_min:.0f} dk   Uzunluk {res.total_length_m/1000:.1f} km")
    print(f"Yumuşatma sonrası {len(res.segments)} segment "
          f"(~{res.total_length_m / max(len(res.segments), 1):.0f} m/segment)")
    print("-" * 78)
    print(f"{'#':>4}  {'yön°':>5}  {'saat':>5}  {'g.azimut':>8}  {'g.yük':>6}  taraf")
    stride = max(1, len(res.segments) // 30)
    for s in res.segments[::stride]:
        t = s.when.strftime("%H:%M")
        print(f"{s.index:>4}  {s.bearing_deg:>5.0f}  {t:>5}  {s.sun_azimuth_deg:>8.0f}  "
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
    span_arg = next((a for a in argv if ":" in a and a.replace(":", "").isdigit()), None)
    span = tuple(int(x) for x in span_arg.split(":")) if span_arg else None

    departure = (
        datetime.fromisoformat(when_arg).replace(tzinfo=TURKEY_TZ)
        if when_arg else datetime.now(TURKEY_TZ)
    )

    # Küçük akıl sağlığı kontrolü: Bursa'da güneş şu an nerede?
    sp = get_sun(departure, 40.19, 29.06)
    print(f"\nBursa @ {departure:%Y-%m-%d %H:%M} +03  ->  "
          f"güneş azimut {sp.azimuth_deg:.0f}°, yükseklik {sp.altitude_deg:.0f}°\n")

    for rid in route_ids:
        run(rid, departure, span)


if __name__ == "__main__":
    main(sys.argv[1:])
