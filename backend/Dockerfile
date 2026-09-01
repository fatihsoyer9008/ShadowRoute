# Gölge Rota backend — ince FastAPI servisi
FROM python:3.12-slim

WORKDIR /app

# Bağımlılıklar (suncalc numpy wheel'i çeker; derleyici gerekmez)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Burulaş yanıt cache'i buraya yazılır — compose'da volume ile kalıcı yapılıyor
RUN mkdir -p app/data/.cache

EXPOSE 8000

# --proxy-headers: Caddy arkasında doğru şema/host
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
