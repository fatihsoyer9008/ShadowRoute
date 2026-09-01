# ShadowRoute · Gölge Rota

Bursa'da otobüs / BursaRay yolculuğunda güneşin hangi taraftan geleceğini
hesaplayıp "hangi koltuğa otur" önerisi veren asistan.

- [`plan.md`](plan.md) — proje planı ve fazlar
- [`backend/`](backend/) — çekirdek algoritma + FastAPI + Burulaş istemcisi
- [`mobile/`](mobile/) — Flutter MVP (hat ara/seç → yön → gölge koltuk önerisi)
- [`deploy/`](deploy/) — Hetzner (Docker + Caddy) deploy yapılandırması

**Web uygulaması (masaüstü/tarayıcı):** https://app.golgerota.116-202-14-23.sslip.io
**Android APK:** [GitHub sürümleri](https://github.com/fatihsoyer9008/ShadowRoute/releases/latest) · [hızlı ayna](https://golgerota.116-202-14-23.sslip.io/dl/)
**Canlı API:** https://golgerota.116-202-14-23.sslip.io/routes

## Hızlı başlangıç

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.poc bursaray-m1 2026-09-01T18:15   # çekirdek demo
python -m scripts.fetch_route M1                     # canlı Burulaş verisi
python -m pytest
uvicorn app.main:app --reload                        # API :8000
```

```bash
# Mobil — varsayılan olarak canlı API'yi kullanır
cd mobile
flutter run                                                # canlı backend
flutter run --dart-define=API_BASE=http://localhost:8000   # yerel backend (web/masaüstü)
```
