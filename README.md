# ShadowRoute · Gölge Rota

Bursa'da otobüs / BursaRay yolculuğunda güneşin hangi taraftan geleceğini
hesaplayıp "hangi koltuğa otur" önerisi veren asistan.

- [`plan.md`](plan.md) — proje planı ve fazlar
- [`backend/`](backend/) — çekirdek algoritma + FastAPI + Burulaş istemcisi
- [`mobile/`](mobile/) — Flutter MVP (hat seç → yön → gölge koltuk önerisi)

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
# Mobil (backend :8000 ayaktayken)
cd mobile
flutter run --dart-define=API_BASE=http://localhost:8000   # web/masaüstü
# Android emülatör: API_BASE=http://10.0.2.2:8000 (varsayılan)
```
