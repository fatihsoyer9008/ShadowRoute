"""Güneş konumu sarmalayıcısı.

Tek dış bağımlılık `suncalc` (suncalc.js portu). suncalc'ın azimut tanımı
"güneyden batıya doğru, radyan" (0 = Güney, +PI/2 = Batı). Biz her yerde
pusula açısı kullanıyoruz (0 = Kuzey, 90 = Doğu, saat yönünde), o yüzden
çeviriyoruz: compass = degrees(azimuth) + 180.

Bu modül kasıtlı ince tutuldu; ileride suncalc yerine pvlib/astral koymak
istersen sadece burayı değiştirirsin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from suncalc import get_position

# Türkiye 2016'dan beri yaz saati uygulamıyor; sabit UTC+3.
TURKEY_TZ = timezone(timedelta(hours=3), name="+03")


@dataclass(frozen=True)
class SunPosition:
    azimuth_deg: float   # pusula açısı: 0 = Kuzey, 90 = Doğu, saat yönünde
    altitude_deg: float  # ufuk üstü yükseklik; < 0 => güneş batmış

    @property
    def is_up(self) -> bool:
        return self.altitude_deg > 0.0

    @property
    def horizontality(self) -> float:
        """Işığın yatay bileşeni: altitude 0'da 1.0, tam tepede (90) 0.0.

        Yandan gelen ışının şiddetiyle orantılı; öğlen güneşi yüksekken
        'sağ/sol' farkının neden azaldığını bu terim yakalıyor.
        """
        if self.altitude_deg <= 0.0:
            return 0.0
        return math.cos(math.radians(self.altitude_deg))


def get_sun(when: datetime, lat: float, lon: float) -> SunPosition:
    if when.tzinfo is None:
        raise ValueError("`when` timezone-aware olmalı (örn. sun.TURKEY_TZ)")
    pos = get_position(when, lon, lat)  # suncalc imzası: (date, lng, lat)
    compass = (math.degrees(float(pos["azimuth"])) + 180.0) % 360.0
    return SunPosition(azimuth_deg=compass, altitude_deg=math.degrees(float(pos["altitude"])))
