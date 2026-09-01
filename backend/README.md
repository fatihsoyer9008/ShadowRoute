# Gölge Rota — Backend (PoC)

Bir güzergah + kalkış zamanı verildiğinde, güneşin yolculuk boyunca hangi
taraftan geldiğini segment segment hesaplayıp "hangi tarafa otur" önerisi üretir.

## Kurulum

Venv repo kökünde tutuluyor (`C:\ShadowRoute\.venv`), backend/ altında değil:

```powershell
# repo kökünden
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Aşağıdaki komutları `backend/` klasöründen çalıştır (venv aktifken).
Sunucu:  `uvicorn app.main:app --host 0.0.0.0 --port 8000`
(venv aktif değilse: `C:\ShadowRoute\.venv\Scripts\uvicorn.exe ... --app-dir C:\ShadowRoute\backend`)

## PoC scripti (Burulaş'a dokunmadan)

```bash
python -m scripts.poc                              # tüm rotalar, "şimdi"
python -m scripts.poc bursaray-m1 2026-09-01T18:15
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
| `GET /routes` | Elle bakımı yapılan hatlar (tünel bölgeleri ayarlı) |
| `GET /search?q=38` | Burulaş'ta hat arar → `[{id: "live-<hatNo>", code, name, mode}]` |
| `GET /routes/{id}?direction=forward` | Hat detayı; `direction` verilirse `stops` o yöndeki sıralı liste |
| `GET /routes/{id}/shadow?when=ISO&direction=&from=&to=` | Analiz. `from`/`to` = o yöndeki durak sırası (0-tabanlı) → duraktan durağa. Boşsa tüm hat. |

`live-<hatNo>` id'leri Burulaş'tan anında çekilir: tünel bölgesi yok, halka
ise dönüş noktası `auto_loop_split` ile tahmin edilir. Çekilen polyline/durak
verisi `burulas` katmanında **bellek + disk** (`data/.cache/`, 12 saat)
cache'li — sunucu yeniden başlasa da korunur.

**Burulaş erişilemezse:** (1) diskteki bayat veri kullanılır; (2) hatNo elle
ayarlı bir hatsa (GeoJSON `hat_no`) doğrudan o hat döner; (3) `/search` elle
bakılan hatlar içinde arar.

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
python -m pytest        # 45 test, ağ gerektirmez
```

## Mimari (ince backend)

```
app/
  core/
    geo.py      bearing + haversine + polyline yumuşatma (saf matematik)
    sun.py      suncalc sarmalayıcı — azimut'u pusula açısına çevirir
    shadow.py   ÇEKIRDEK: analyze() -> RouteShadow
  data/routes/  statik GeoJSON hatlar (MVP'de DB yok)
  data/tunnel_zones.json  M1/M2 ortak yeraltı bölgeleri (tunnel_zone_refs ile bağlanır)
  routes_repo.py GeoJSON yükleyici + ortak tünel çözümleme + gidiş/dönüş
  burulas.py    Burulaş API istemcisi
  main.py       FastAPI kabuğu
scripts/poc.py        terminal demo (statik hatlar)
scripts/fetch_route.py canlı Burulaş çekme + analiz
```

Bir rota hem kendi `tunnel_zones` dizisini hem de `tunnel_zone_refs`
(örn. `["bursaray-acemler", "bursaray-merkez"]`) ile ortak bölgeleri
kullanabilir; `routes_repo` ikisini birleştirir.

**Kapalı halka hatlar** (ör. 38 — Terminal ↔ Heykel): GeoJSON'da `loop_split`
= dönüş noktasının koordinat indeksi. `path("forward")` = başlangıç→dönüş,
`path("backward")` = dönüş→başlangıç (halka zaten geri döndüğü için ters
çevrilmez). Bölünmezse tek yönlü halka ~%50/50 sonuç verirdi.

## Algoritma özeti

0. **Polyline yumuşatma** (`geo.smooth_route`): ham Burulaş güzergahı önce
   Douglas–Peucker (`epsilon ≈ 25 m`) ile titremeden arındırılır, sonra ~40 m
   eşit aralıklarla yeniden örneklenir. Böylece GPS logunun yoğun/seyrek
   noktalaması segment ağırlıklarını bozmaz, gidiş açıları oynamaz.
1. Rota ardışık noktalardan segmentlere bölünür.
2. Her segmentin **gidiş yönü** (pusula açısı) hesaplanır.
3. Ortalama hızla yolcunun o segmente **ne zaman** geleceği bulunur; o an + segment
   orta noktası için **güneş azimut & yüksekliği** alınır (suncalc).
4. `rel = güneş_azimut − gidiş_yönü` (−180..180). `+` ⇒ güneş sağda.
   - `|rel| ≤ 35°` ⇒ ÖN, `|rel| ≥ 145°` ⇒ ARKA, aksi halde SOL/SAĞ.
5. **Yatay şiddet** `cos(altitude)` ile ağırlıklandırılır → öğlen yüksek güneşte
   sağ/sol farkı küçülür. Güneş yüksekliği ≤ 0 ⇒ etki 0 (gece).
6. **Tünel/yeraltı bölgeleri** GeoJSON `tunnel_zones` = `(lat, lon, yarıçap_m)`
   daireleri. Segment orta noktası bir dairenin içindeyse etki 0. Coğrafi
   olduğu için yumuşatmadan ve gidiş/dönüş yönünden etkilenmez.
7. Segment uzunluğu × yatay şiddet toplanır; sol vs sağ kıyaslanıp **az güneş
   alan taraf** önerilir. Ön camdan güneş için "kaçış yok" uyarısı eklenir.

> Not: Gerçekten çok dönen bir hat (ör. 38 kampüs turu) için sol/sağ ~%50/50
> çıkabilir — bu doğru cevaptır, o hatta net bir gölge tarafı yoktur. (38
> halka hattı `loop_split` ile ikiye bölününce net sonuç veriyor.)

`analyze()` yumuşatma parametreleri: `simplify_epsilon_m` (0 = kapalı),
`resample_step_m` (None = kapalı), `tunnel_zones`.

### Bilinçli basitleştirmeler (V1)

- Bina/ağaç gölgeleri modellenmez (şehir içinde gerçek etkiyi azaltır).
- Cam rengi / araç tipi hesaba katılmaz.
- Yolcunun tüm hattı bindiği varsayılır ("nereden nereye" V2).
- Tüm hatlar **gerçek Burulaş verisi**: `bursaray-m1` (1531), `bursaray-m2`
  (1519), `bus-38` (1012), `bus-4g` (1121). Yeraltı bölgeleri tr.wikipedia
  istasyon listesinden. 38 ve 4G kapalı halka → `loop_split`.
