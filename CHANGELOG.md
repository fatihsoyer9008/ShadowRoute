# Değişiklik günlüğü

## v0.1.1 — 2026-09-01

- **Yön seçimi kaldırıldı.** Artık sadece biniş ve iniş durağını seçiyorsun;
  yön bu sıradan çıkıyor. Düz hatta ters durak sırası = ters yön, halka hatta
  turu tamamlar. Bir adım az.
- Masaüstü/tarayıcı için hosted web uygulaması: https://app.golgerota.116-202-14-23.sslip.io
- APK: per-ABI (arm64 ~17 MB) + hızlı ayna (GitHub bazı bölgelerde yavaş).
- Backend: bellek + disk cache, Burulaş çökünce statik hat / bayat veri fallback.

## v0.1.0 — 2026-09-01 (ilk sürüm)

Bursa'da otobüs / BursaRay yolculuğunda güneşin hangi taraftan geleceğini
hesaplayıp "hangi koltuğa otur" önerisi veren MVP.

### Çekirdek
- Güneş-tarafı algoritması: rota segment segment analiz edilir, her segment için
  gidiş yönü ile güneş azimut/yükseklik açısı karşılaştırılır → SOL / SAĞ / ÖN /
  ARKA / YOK. `cos(altitude)` ile ağırlıklandırma (öğlen yüksek güneşte fark azalır),
  gece = etki yok, güneş yolculuk boyunca ilerletilir.
- Ham GPS polyline'ları analiz öncesi yumuşatılır (Douglas–Peucker + yeniden örnekleme).
- Dürüst uyarılar: ön camdan güneş ("kaçış yok"), alçak güneş (gündoğumu/batımı), tünel.

### Veri
- 4 hat gerçek Burulaş verisiyle: **BursaRay M1, M2, 38, 4G**.
- Yeraltı/tünel bölgeleri coğrafi dairelerle (kaynak: tr.wikipedia BursaRay istasyon
  listesi). M1/M2 merkez tüneli ortak tanımlı.
- Kapalı halka hatlar (38, 4G) otomatik iki bacağa bölünür.
- Herhangi bir Bursa hattı canlı aranıp analiz edilebilir (`/search`).

### Uygulama (Android)
- Hat ara/seç → duraktan durağa → zaman → gölge koltuk önerisi.
- Şematik koltuk diyagramı, rota boyunca güneş haritası, taraf dağılım çubuğu.
- Backend canlı: `https://golgerota.116-202-14-23.sslip.io` (HTTPS).

### Bilinen sınırlar
- Bina/ağaç gölgeleri modellenmez (şehir içinde gerçek etkiyi azaltır).
- Cam rengi / araç tipi hesaba katılmaz.
- **Saha testi yapılmadı** — öneriler henüz gerçek yolculukla doğrulanmadı.
- APK debug anahtarıyla imzalı (yan yükleme için; Play Store'a hazır değil).
