"""Burulaş'tan canlı güzergah çekip gölge analizini gerçek veriyle koştur.

    python -m scripts.fetch_route 38                       # analiz, "şimdi"
    python -m scripts.fetch_route M1 2026-09-01T18:15 backward
    python -m scripts.fetch_route 38 --save                # data/routes/ altına GeoJSON yaz

Faz 0 kontrolü: API gerçekten polyline veriyor mu? Bu script onu kanıtlar.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from app import burulas
from app.core.shadow import Side, analyze
from app.core.sun import TURKEY_TZ

BAR = {Side.LEFT: "<< SOL ", Side.RIGHT: " SAG >>", Side.FRONT: "^^ ON  ",
       Side.BACK: "vv ARKA", Side.NONE: "  --   "}
ROUTES_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "routes"


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__)
        return
    code = argv[0]
    save = "--save" in argv
    rest = [a for a in argv[1:] if not a.startswith("--")]
    when_arg = next((a for a in rest if a[:4].isdigit()), None)
    direction = "backward" if "backward" in rest else "forward"
    departure = (
        datetime.fromisoformat(when_arg).replace(tzinfo=TURKEY_TZ)
        if when_arg else datetime.now(TURKEY_TZ)
    )

    route = burulas.find_route(code)
    hat_no = route["hatNo"]
    print(f"\nHat: {route['kod']}  (hatNo={hat_no})  '{route.get('aciklama', '')}'")

    paths = burulas.directional_paths(hat_no)
    stops = burulas.route_stops(hat_no)
    coords = paths[direction]
    print(f"Polyline: forward={len(paths['forward'])} nokta, "
          f"backward={len(paths['backward'])} nokta | duraklar={len(stops)}")
    print(f"Analiz yönü: {direction}  |  kalkış {departure:%Y-%m-%d %H:%M} +03\n")

    speed = 32.0 if route["kod"].upper().startswith(("M", "T")) else 18.0
    res = analyze(coords, departure, avg_speed_kmh=speed)

    print("-" * 70)
    step = max(1, len(res.segments) // 25)  # uzun polyline'ı seyrek bas
    for s in res.segments[::step]:
        print(f"{s.index:>4}  yön {s.bearing_deg:>5.0f}°  {s.when:%H:%M}  "
              f"güneş az {s.sun_azimuth_deg:>5.0f}° yük {s.sun_altitude_deg:>4.0f}°  "
              f"{BAR[s.side]}")
    print("-" * 70)
    for side in (Side.LEFT, Side.RIGHT, Side.FRONT, Side.BACK, Side.NONE):
        print(f"  {side.tr:>4}: %{res.pct_length(side):>4.0f}")
    print("-" * 70)
    print(f"  >>> {res.headline}")
    for n in res.notes:
        print(f"      - {n}")
    print()

    if save:
        fwd = paths["forward"]
        feature = {
            "type": "Feature",
            "properties": {
                "id": f"burulas-{route['kod'].lower()}",
                "name": f"{route['kod']} — {route.get('aciklama', '')}".strip(" —"),
                "mode": "metro" if speed >= 30 else "bus",
                "avg_speed_kmh": speed,
                "tunnel_zones": [],
                "source": f"Burulaş API (hatNo={hat_no}), çekildi {datetime.now(TURKEY_TZ):%Y-%m-%d}",
                "hat_no": hat_no,
                "stops": [s.get("stopName") for s in stops],
                "stop_coords": [[float(s["longitude"]), float(s["latitude"])] for s in stops],
            },
            "geometry": {"type": "LineString",
                         "coordinates": [[lon, lat] for lat, lon in fwd]},
        }
        out = ROUTES_DIR / f"{feature['properties']['id']}.geojson"
        out.write_text(json.dumps(feature, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  yazıldı: {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
