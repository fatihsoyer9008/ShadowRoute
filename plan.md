# Gölge Rota (Shadow Route) — Proje Planı

## 1. Proje Özeti ve Amacı
Kullanıcıların otobüs / metro (BursaRay) yolculuğu sırasında güneşin hangi
taraftan vuracağını hesaplayarak "en gölge ve rahat koltuğu" seçmesine yardım
eden ulaşım asistanı. İlk etap: Bursa merkez, Burulaş verisi.

## 2. Mimari ve Teknoloji Yığını
- **Frontend (Mobil):** Flutter (Dart)
- **Backend (ince katman):** FastAPI (Python) — yalnızca **proxy + cache + analiz**.
  Ağır iş yok; güneş matematiği hafif.
- **Veritabanı:** MVP'de **yok**. Rotalar statik GeoJSON dosyaları. Kullanıcı
  hesabı/favori gelince Postgres eklenir.
- **Araçlar:** VS Code, Git, GitHub
- **Dış API'ler:**
  - Burulaş API (hat/durak/güzergah — `erenbozaci/fetchingburulasapi` referans, **resmi değil**)
  - suncalc (güneş azimut & yükseklik)
  - OpenWeather (opsiyonel, V2)

## 3. MVP Kapsamı (daraltılmış)
Gerçek minimum:
- **1–3 hat**, statik GeoJSON olarak gömülü (Burulaş çökse de çalışır).
- Gidiş / dönüş yönü seçimi.
- "Şu an" için analiz.
- **Metin sonucu:** "SAĞ tarafa otur. Yolculuğun ~%70'inde güneş sol taraftan
  gelecek." + tünel/ön-cam/alçak-güneş uyarıları.

Arama ekranı ve koltuk illüstrasyonları → ikinci adım.

## 4. Fazlar

### Faz 0 — API risk kontrolü  ✅ TAMAM
- [x] Burulaş endpoint'lerinden hat + polyline çekilebiliyor **(EVET)**
  - Base URL: `https://bursakartapi.abys-web.com` (ABYS / BursaKart backend)
  - Kimlik doğrulama **yok**, POST + JSON gövde, `Origin: https://www.bursakart.com.tr`
  - `POST /api/static/routeandstation` `{"keyword":"38"}` → hat/durak arama
  - `POST /api/static/routecoordinate` `{"keyword":"<hatNo>"}` → **polyline** (sequence + routeDirection)
  - `POST /api/static/routestat` `{"routeCode":<hatNo>}` → sıralı duraklar
  - Yön: `routeDirection` `G`=gidiş / `D`=dönüş; bazı hatlarda sadece `R` (tek yön) → biz ters çeviriyoruz
  - Cevap alan adı `logitude` (API tarafında typo, kodda ele alındı)
  - İstemci: `app/burulas.py`, canlı demo: `python -m scripts.fetch_route M1`
- [x] Plan B hâlâ geçerli: `routes_repo` statik GeoJSON'a düşebiliyor
- **Bulgu:** ham polyline gürültülü (512 nokta/dönüş). RDP + yeniden örnekleme
  eklendi (`geo.smooth_route`, Faz 2). Not: çok dönen hatlarda (38 kampüs turu)
  sol/sağ ~%50/50 çıkması **normal** — o hatta net gölge tarafı yok; metro
  hatları net sonuç veriyor.

### Faz 1 — Çekirdek algoritma (Backend)  ✅ PoC HAZIR
- [x] `geo.py` — bearing + haversine
- [x] `sun.py` — suncalc sarmalayıcı (azimut → pusula açısı)
- [x] `shadow.py` — `analyze()`: segment sınıflandırma + öneri
  - [x] `altitude ≤ 0` ⇒ etki 0 (gece)
  - [x] `cos(altitude)` ile yatay-şiddet ağırlığı (öğlen yüksek güneş)
  - [x] tünel/yeraltı segmentleri ⇒ etki 0 (GeoJSON `tunnel_segments`)
  - [x] ön cam / arka cam / alçak güneş uyarıları
  - [x] yolculuk boyunca güneşi ilerletme (ortalama hız)
- [x] `scripts/poc.py` — terminal demo
- [x] pytest testleri (14)

### Faz 2 — Burulaş entegrasyonu
- [x] `app/burulas.py` — API istemcisi (search / routecoordinate / routestat)
- [x] `scripts/fetch_route.py` — canlı çek + analiz + `--save` ile GeoJSON yaz
- [x] **Polyline yumuşatma** — `geo.smooth_route` (Douglas–Peucker + yeniden
      örnekleme), `analyze()` içine gömülü
- [x] Tünel gösterimi coğrafi bölgeye çevrildi (`tunnel_zones`, yön-bağımsız)
- [ ] Tünel bölgelerini gerçek BursaRay (M1/M2) güzergahına göre ayarla
- [ ] Basit cache (dosya/SQLite/Redis) — rotalar nadiren değişir
- [ ] API çökerse statik GeoJSON'a otomatik fallback (routes_repo ile birleştir)

### Faz 3 — Mobil (Flutter)  🚧 MVP iskeleti hazır (`mobile/`)
- [x] Sade UI: hat dropdown + yön SegmentedButton + zaman seçici + sonuç kartı
- [x] FastAPI servis katmanı (`services/api.dart`), loading / Türkçe hata durumları
- [x] Koltuk grafiği (`SeatDiagram`) + taraf dağılım çubuğu + not listesi
- [x] Uçtan uca doğrulandı (Flutter web → backend → motor)
- [ ] Gerçek cihaz/emülatör testi, hat arama ekranı, güneşli segment haritası
- [ ] `API_BASE` prod adresi + HTTPS (şimdilik dev cleartext)

### Faz 4 — Test & saha
- [ ] Gündoğumu/günbatımı edge-case testleri
- [ ] Bilinen güzergahlarda canlı deneme, gerçeklikle karşılaştırma
- [ ] Cache ile hesap süresini düşür

## 5. V2 Özellikleri
- **Zaman seçici:** "Yarın 14:00" sorgusu (backend zaten destekliyor).
- **Nereden nereye:** kullanıcının bindiği kısmı hesaba kat.
- **Hava durumu:** kapalıysa "hava bulutlu, istediğin yere geç kanka".
- **Bina gölgeleri:** şehir merkezi için yaklaşık gölge modeli (zor, düşük öncelik).

## 6. Bilinçli olarak dışarıda bırakılanlar (V1)
- Bina/ağaç gölgeleri
- Cam rengi / araç tipi
- Yolcunun kısmi biniş varsayımı (tüm hat varsayılıyor)
