# ShadowRoute · Gölge Rota

Bursa'da otobüs / BursaRay yolculuğunda güneşin hangi taraftan geleceğini
hesaplayıp "hangi koltuğa otur" önerisi veren asistan.

- [`plan.md`](plan.md) — proje planı ve fazlar
- [`backend/`](backend/) — çekirdek algoritma + FastAPI (PoC hazır)

## Hızlı başlangıç

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.poc bursaray-t1 2026-09-01T18:15
python -m pytest
```
