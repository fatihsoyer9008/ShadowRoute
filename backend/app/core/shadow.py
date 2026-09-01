"""Çekirdek algoritma: bir güzergah + kalkış zamanı -> hangi tarafa oturmalı.

Fikir:
  1. Rotayı ardışık GPS noktalarından oluşan segmentlere böl.
  2. Her segment için gidiş yönünü (bearing) hesapla.
  3. Yolcunun o segmente yaklaşık ne zaman geleceğini bul (ortalama hızla) ve
     o an/o konum için güneşin azimut + yüksekliğini al.
  4. Güneşi otobüsün gidiş yönüne göre sınıflandır: SOL / SAĞ / ÖN / ARKA / YOK.
  5. Segment uzunluğu ve ışığın yatay şiddetiyle ağırlıklandırıp topla.
  6. Yanal (sol/sağ) maruz kalmayı kıyasla -> öneri.

Ham Burulaş polyline'ları gürültülü (rotari/sapak titremesi) -> analiz öncesi
`smooth_route` ile temizlenir (RDP + eşit aralıklı yeniden örnekleme).

Bilinçli basitleştirmeler (README'de not düşülüyor):
  - Bina/ağaç gölgeleri modellenmiyor (şehir içinde gerçek etkiyi azaltır).
  - Tünel/yeraltı bölgeleri elle işaretleniyor (coğrafi daire; güneş etkisi = 0).
  - Cam rengi / otobüs tipi hesaba katılmıyor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .geo import (
    Point,
    haversine_m,
    initial_bearing_deg,
    midpoint,
    normalize_180,
    point_in_zones,
    smooth_route,
)
from .sun import SunPosition, get_sun

# |güneş - gidiş yönü| bu koninin içindeyse ön/arka camdan sayılır (yan koltuk kurtarmaz).
FRONT_BACK_CONE_DEG = 35.0

# Yanal maruz kalma toplamı rota uzunluğunun bu oranından küçükse "fark etmez" deriz.
NEGLIGIBLE_LATERAL_RATIO = 0.06


class Side(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"
    NONE = "none"  # güneş batık ya da tünel

    @property
    def tr(self) -> str:
        return {"left": "sol", "right": "sağ", "front": "ön", "back": "arka", "none": "yok"}[self.value]


@dataclass(frozen=True)
class SegmentAnalysis:
    index: int
    length_m: float
    bearing_deg: float
    mid: Point                # segment orta noktası (lat, lon) — harita/görselleştirme için
    when: datetime
    sun_azimuth_deg: float
    sun_altitude_deg: float
    side: Side
    lateral_exposure: float   # 0..1, yandan gelen ışık şiddeti (uzunlukla çarpılmadan)
    frontal_exposure: float   # 0..1, ön/arka camdan gelen ışık şiddeti
    in_tunnel: bool


@dataclass
class RouteShadow:
    departure: datetime
    total_length_m: float
    trip_duration_min: float
    segments: list[SegmentAnalysis] = field(default_factory=list)

    # uzunluk payları (metre)
    length_by_side: dict[Side, float] = field(default_factory=dict)
    # uzunluk * yatay şiddet ile ağırlıklı maruz kalma (karar metriği)
    exposure_by_side: dict[Side, float] = field(default_factory=dict)

    recommended_side: Side = Side.NONE
    sun_up_fraction: float = 0.0
    headline: str = ""
    notes: list[str] = field(default_factory=list)

    def pct_length(self, side: Side) -> float:
        if self.total_length_m <= 0:
            return 0.0
        return 100.0 * self.length_by_side.get(side, 0.0) / self.total_length_m

    def to_dict(self) -> dict:
        return {
            "departure": self.departure.isoformat(),
            "trip_duration_min": round(self.trip_duration_min, 1),
            "total_length_km": round(self.total_length_m / 1000.0, 2),
            "sun_up_fraction": round(self.sun_up_fraction, 2),
            "recommended_side": self.recommended_side.value,
            "headline": self.headline,
            "notes": self.notes,
            "breakdown_pct_of_route": {
                s.value: round(self.pct_length(s), 1)
                for s in (Side.LEFT, Side.RIGHT, Side.FRONT, Side.BACK, Side.NONE)
            },
            "exposure_weighted": {
                s.value: round(self.exposure_by_side.get(s, 0.0), 1)
                for s in (Side.LEFT, Side.RIGHT, Side.FRONT, Side.BACK)
            },
            "segments": [
                {
                    "index": s.index,
                    "length_m": round(s.length_m),
                    "bearing_deg": round(s.bearing_deg, 1),
                    "lat": round(s.mid[0], 6),
                    "lon": round(s.mid[1], 6),
                    "when": s.when.isoformat(),
                    "sun_azimuth_deg": round(s.sun_azimuth_deg, 1),
                    "sun_altitude_deg": round(s.sun_altitude_deg, 1),
                    "side": s.side.value,
                    "in_tunnel": s.in_tunnel,
                }
                for s in self.segments
            ],
        }


def _classify(bearing_deg: float, sun: SunPosition, in_tunnel: bool) -> tuple[Side, float, float]:
    """(side, lateral_exposure, frontal_exposure) döner. Exposure'lar 0..1."""
    if in_tunnel or not sun.is_up:
        return Side.NONE, 0.0, 0.0

    rel = normalize_180(sun.azimuth_deg - bearing_deg)  # + => güneş sağda
    a = abs(rel)
    if a <= FRONT_BACK_CONE_DEG:
        side = Side.FRONT
    elif a >= 180.0 - FRONT_BACK_CONE_DEG:
        side = Side.BACK
    elif rel > 0:
        side = Side.RIGHT
    else:
        side = Side.LEFT

    h = sun.horizontality  # altitude yükseldikçe düşer
    lateral = h * abs(math.sin(math.radians(rel)))   # 90°'de en güçlü
    frontal = h * abs(math.cos(math.radians(rel)))   # 0/180°'de en güçlü
    return side, lateral, frontal


def analyze(
    coords: list[Point],
    departure: datetime,
    *,
    avg_speed_kmh: float = 18.0,
    tunnel_zones: list[tuple[float, float, float]] | None = None,
    simplify_epsilon_m: float = 25.0,
    resample_step_m: float | None = 40.0,
) -> RouteShadow:
    """
    coords             : (lat, lon) noktaları, rota sırasıyla (ham polyline olabilir).
    departure          : timezone-aware kalkış zamanı.
    avg_speed_kmh      : güneşi yolculuk boyunca ilerletmek için kaba hız.
    tunnel_zones       : güneş görmeyen bölgeler, (lat, lon, yarıçap_m) daireleri.
                         Segment orta noktası bir dairenin içindeyse etki = 0.
    simplify_epsilon_m : RDP eşiği; GPS titremesini temizler (0 = kapalı).
    resample_step_m    : eşit aralıklı yeniden örnekleme adımı (None = kapalı).
    """
    if len(coords) < 2:
        raise ValueError("En az 2 nokta gerekli")
    if departure.tzinfo is None:
        raise ValueError("`departure` timezone-aware olmalı")

    coords = smooth_route(
        coords,
        simplify_epsilon_m=simplify_epsilon_m,
        resample_step_m=resample_step_m,
    )
    if len(coords) < 2:
        raise ValueError("Yumuşatma sonrası yeterli nokta kalmadı")

    zones = tunnel_zones or []

    def in_tunnel(mid: Point) -> bool:
        return point_in_zones(mid, zones)

    speed_ms = max(avg_speed_kmh, 1.0) * 1000.0 / 3600.0
    cum_time_s = 0.0

    segments: list[SegmentAnalysis] = []
    length_by_side: dict[Side, float] = {s: 0.0 for s in Side}
    exposure_by_side: dict[Side, float] = {s: 0.0 for s in Side}
    sun_up_length = 0.0
    front_length = 0.0  # ön camdan güneş * şiddet * uzunluk (kaçış yok uyarısı)
    back_length = 0.0   # arka camdan güneş — parlama sorunu değil, sadece bilgi

    for i in range(len(coords) - 1):
        a, b = coords[i], coords[i + 1]
        length = haversine_m(a, b)
        if length < 1e-6:
            continue
        mid_time = departure + timedelta(seconds=cum_time_s + (length / speed_ms) / 2.0)
        cum_time_s += length / speed_ms

        bearing = initial_bearing_deg(a, b)
        mid = midpoint(a, b)
        sun = get_sun(mid_time, mid[0], mid[1])
        tunnel = in_tunnel(mid)
        side, lateral, frontal = _classify(bearing, sun, tunnel)

        segments.append(
            SegmentAnalysis(
                index=i,
                length_m=length,
                bearing_deg=bearing,
                mid=mid,
                when=mid_time,
                sun_azimuth_deg=sun.azimuth_deg,
                sun_altitude_deg=sun.altitude_deg,
                side=side,
                lateral_exposure=lateral,
                frontal_exposure=frontal,
                in_tunnel=tunnel,
            )
        )

        length_by_side[side] += length
        exposure_by_side[side] += length * lateral
        if sun.is_up and not tunnel:
            sun_up_length += length
        if side is Side.FRONT:
            front_length += length * frontal
        elif side is Side.BACK:
            back_length += length * frontal

    total_length = sum(s.length_m for s in segments)
    duration_min = cum_time_s / 60.0
    sun_up_fraction = sun_up_length / total_length if total_length else 0.0

    result = RouteShadow(
        departure=departure,
        total_length_m=total_length,
        trip_duration_min=duration_min,
        segments=segments,
        length_by_side=length_by_side,
        exposure_by_side=exposure_by_side,
        sun_up_fraction=sun_up_fraction,
    )

    _recommend(result, total_length, front_length, back_length)
    return result


def _recommend(
    r: RouteShadow, total_length: float, front_length: float, back_length: float
) -> None:
    left = r.exposure_by_side.get(Side.LEFT, 0.0)
    right = r.exposure_by_side.get(Side.RIGHT, 0.0)
    lateral_total = left + right

    if r.sun_up_fraction < 0.02:
        r.recommended_side = Side.NONE
        r.headline = "Güneş yok (gece / güneş ufkun altında) — koltuk fark etmez, nereye istersen otur."
        return

    tunnel_pct = r.pct_length(Side.NONE)
    if tunnel_pct >= 15.0:
        r.notes.append(f"Rotanın ~%{tunnel_pct:.0f}'i yeraltında/tünelde — o kısımda güneş etkisi yok.")

    # Yanal segmentlerin ortalama güneş yüksekliği (yüksekse "otur ama etki hafif").
    lat_segs = [s for s in r.segments if s.side in (Side.LEFT, Side.RIGHT)]
    mean_alt = sum(s.sun_altitude_deg for s in lat_segs) / len(lat_segs) if lat_segs else 0.0

    if lateral_total < NEGLIGIBLE_LATERAL_RATIO * total_length:
        r.recommended_side = Side.NONE
        if front_length >= 0.20 * total_length:
            r.headline = "Güneş büyük ölçüde ön camdan geliyor — sağ/sol koltuk pek fark etmez."
        elif back_length >= 0.20 * total_length:
            r.headline = "Güneş arkadan geliyor — gözünü almaz, istediğin tarafa oturabilirsin."
        else:
            r.headline = "Güneş neredeyse tam tepede — sağ/sol koltuk farkı çok küçük."
    else:
        # Daha az güneş alan tarafı öner.
        if left <= right:
            r.recommended_side = Side.LEFT
            worse, worse_pct = Side.RIGHT, r.pct_length(Side.RIGHT)
        else:
            r.recommended_side = Side.RIGHT
            worse, worse_pct = Side.LEFT, r.pct_length(Side.LEFT)
        share = 100.0 * max(left, right) / lateral_total
        r.headline = (
            f"{r.recommended_side.tr.upper()} tarafa otur. "
            f"Yolculuğun ~%{worse_pct:.0f}'inde güneş {worse.tr} taraftan gelecek "
            f"(yanal maruz kalmanın ~%{share:.0f}'i o tarafta)."
        )
        if mean_alt >= 55.0:
            r.notes.append(
                "Güneş yüksekte (öğle civarı) — doğru tarafta bile etki hafif olur."
            )

    if front_length >= 0.20 * total_length:
        pct = 100.0 * front_length / total_length
        r.notes.append(
            f"Yolun ~%{pct:.0f}'inde güneş ön camdan geliyor; o bölümde koltuk seçimi kurtarmaz."
        )
    if back_length >= 0.30 * total_length:
        pct = 100.0 * back_length / total_length
        r.notes.append(f"Yolun ~%{pct:.0f}'inde güneş arkadan; parlama sorunu olmaz.")

    # Alçak güneş uyarısı — yalnız güneş yan/ön taraftayken anlamlı (arkadaysa dert değil).
    low = [
        s for s in r.segments
        if 0.0 < s.sun_altitude_deg < 12.0 and s.side in (Side.LEFT, Side.RIGHT, Side.FRONT)
    ]
    if low:
        r.notes.append("Güneş alçakta (gündoğumu/günbatımı) — gözü en çok alan saat dilimindesin.")
