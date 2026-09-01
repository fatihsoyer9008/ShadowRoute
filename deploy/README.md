# Deploy — Hetzner (116.202.14.23)

Sunucu Caddy + Docker Compose deseni kullanıyor; her uygulama bir subdomain.
Gölge Rota API: **https://golgerota.116-202-14-23.sslip.io**

## İlk kurulum

```bash
ssh root@116.202.14.23
git clone https://github.com/fatihsoyer9008/ShadowRoute.git /root/GolgeRota
cd /root/GolgeRota
docker compose -f deploy/docker-compose.yml up -d --build   # -> 127.0.0.1:8010
```

Caddyfile'a (`/etc/caddy/Caddyfile`) blok ekle, sonra `systemctl reload caddy`:

```
golgerota.116-202-14-23.sslip.io {
	reverse_proxy 127.0.0.1:8010
}
```

## Güncelleme

```bash
cd /root/GolgeRota && git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

## Kontrol

```bash
curl -s https://golgerota.116-202-14-23.sslip.io/routes | head -c 200
docker logs golgerota_api --tail 30
```

Mobil uygulamayı bu adrese bağlamak için:

```bash
flutter build apk --release --dart-define=API_BASE=https://golgerota.116-202-14-23.sslip.io
```
