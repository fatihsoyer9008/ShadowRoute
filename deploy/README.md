# Deploy

Sunucu Caddy + Docker Compose deseni kullanıyor; her uygulama bir subdomain
altında, localhost'a bağlı bir port, Caddy ters proxy + otomatik HTTPS.

Sunucuya özel değerler (IP, subdomain, port) `deploy/.env` dosyasında —
takip edilmiyor. Şablon: [`deploy/.env.example`](.env.example).

## İlk kurulum

```bash
ssh root@$SERVER_HOST
git clone <repo-url> /root/GolgeRota && cd /root/GolgeRota
cp deploy/.env.example deploy/.env      # değerleri doldur
docker compose -f deploy/docker-compose.yml up -d --build   # -> 127.0.0.1:$APP_PORT
```

Caddyfile'a (`/etc/caddy/Caddyfile`) blok ekle, `systemctl reload caddy`:

```
$API_SUBDOMAIN {
	reverse_proxy 127.0.0.1:$APP_PORT
}
```

## Güncelleme

```bash
cd /root/GolgeRota && git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

## Kontrol

```bash
curl -s https://$API_SUBDOMAIN/routes | head -c 200
docker logs golgerota_api --tail 30
```

## Mobil uygulamayı canlı API'ye bağlama

```bash
flutter build apk --release --dart-define=API_BASE=https://$API_SUBDOMAIN
```

`mobile/lib/config.dart` içindeki varsayılan `API_BASE` de canlı adresi
gösteriyor; kendi sunucun farklıysa orayı güncelle veya hep `--dart-define` ver.
