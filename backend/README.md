# Gölge Rota — Backend (PoC)

Bir güzergah + kalkış zamanı verildiğinde, güneşin yolculuk boyunca hangi
taraftan geldiğini segment segment hesaplayıp "hangi tarafa otur" önerisi üretir.

## Kurulum

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

## PoC scripti (Burulaş'a dokunmadan)

```bash
python -m scripts.poc                              # tüm rotalar, "şimdi"
python -m scripts.poc bursaray-t1 2026-09-01T18:15
python -m scripts.poc bus-38 2026-06-21T08:00 backward
```

Çıktı: her segment için gidiş yönü, o andaki güneş azimut/yükseklik değeri,
sınıflandırma (SOL/SAĞ/ÖN/ARKA/YOK) ve toplam öneri.

## API

```bash
uvicorn app.main:app --reload
```

| Endpoint | Açıklama |
|---|---|
| `GET /routes` | Tanımlı hatlar |
| `GET /routes/{id}/shadow?when=ISO&direction=forward\|backward` | Analiz. `when` boşsa Türkiye saatiyle şimdi. |

## Canlı Burulaş verisi (Faz 0 — çalışıyor)

```bash
python -m scripts.fetch_route M1                       # BursaRay M1, "şimdi"
python -m scripts.fetch_route 38 2026-09-01T08:00
python -m scripts.fetch_route 38 --save                # data/routes/ altına GeoJSON
```

Base URL `https://bursakartapi.abys-web.com`, kimlik doğrulama yok, POST+JSON.
Detay ve endpoint listesi: [`plan.md`](../plan.md) Faz 0. Resmi/dokümante bir
API değil — sözleşme kırılabilir, o yüzden statik GeoJSON fallback korunuyor.

## Testler

```bash
python -m pytest        # 14 test, ağ gerektirmez
```

## Mimari (ince backend)

```
app/
  core/
    geo.py      bearing + haversine (saf matematik)
    sun.py      suncalc sarmalayıcı — azimut'u pusula açısına çevirir
    shadow.py   ÇEKIRDEK: analyze() -> RouteShadow
  data/routes/  statik GeoJSON hatlar (MVP'de DB yok)
  routes_repo.py GeoJSON yükleyici + gidiş/dönüş ters çevirme
  main.py       FastAPI kabuğu
scripts/poc.py  terminal demo
```

## Algoritma özeti

1. Rota ardışık GPS noktalarından segmentlere bölünür.
2. Her segmentin **gidiş yönü** (pusula açısı) hesaplanır.
3. Ortalama hızla yolcunun o segmente **ne zaman** geleceği bulunur; o an + segment
   orta noktası için **güneş azimut & yüksekliği** alınır (suncalc).
4. `rel = güneş_azimut − gidiş_yönü` (−180..180). `+` ⇒ güneş sağda.
   - `|rel| ≤ 35°` ⇒ ÖN, `|rel| ≥ 145°` ⇒ ARKA, aksi halde SOL/SAĞ.
5. **Yatay şiddet** `cos(altitude)` ile ağırlıklandırılır → öğlen yüksek güneşte
   sağ/sol farkı küçülür. Güneş yüksekliği ≤ 0 ⇒ etki 0 (gece).
6. Tünel/yeraltı segmentleri (GeoJSON `tunnel_segments`) → etki 0.
7. Segment uzunluğu × yatay şiddet toplanır; sol vs sağ kıyaslanıp **az güneş
   alan taraf** önerilir. Ön camdan güneş için "kaçış yok" uyarısı eklenir.

### Bilinçli basitleştirmeler (V1)

- Bina/ağaç gölgeleri modellenmez (şehir içinde gerçek etkiyi azaltır).
- Cam rengi / araç tipi hesaba katılmaz.
- Yolcunun tüm hattı bindiği varsayılır ("nereden nereye" V2).
- GeoJSON koordinatları **sentetik/yaklaşık** — gerçek veri Burulaş'tan gelecek.
