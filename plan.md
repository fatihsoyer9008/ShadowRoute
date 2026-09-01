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

### Faz 0 — API risk kontrolü (1 gün)  ⚠️ önce bu
- [ ] Burulaş endpoint'lerinden gerçekten hat + polyline çekilebiliyor mu?
- [ ] Çekilemiyorsa: 2–3 popüler hattı elle GeoJSON'a al, plan B devrede.

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
- [ ] Rota verisini standart GeoJSON'a normalize eden çekici modül
- [ ] Basit cache (dosya/SQLite/Redis) — rotalar nadiren değişir
- [ ] Tünel segmentlerini gerçek BursaRay güzergahına işaretle

### Faz 3 — Mobil (Flutter)
- [ ] Sade UI: yön seçici + sonuç kartı
- [ ] FastAPI servis katmanı, loading / hata durumları
- [ ] Sonuç görselleştirme (koltuk grafiği, güneşli segment haritası)

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
