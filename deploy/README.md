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

## Web uygulaması (masaüstü/tarayıcı)

Flutter web build'i `app.$API_SUBDOMAIN` altında statik sunuluyor. Native
`.exe` yerine bu — her OS'ta tarayıcıda çalışır, kurulum yok. (Gerçek
Windows .exe için Visual Studio'da "Desktop development with C++" workload'ı
gerekiyor; şimdilik kurulu değil.)

```bash
# yerelde
cd mobile && flutter build web --release
cd build && tar czf web.tgz web && scp -C web.tgz root@$SERVER_HOST:/tmp/
# sunucuda
ssh root@$SERVER_HOST '
  cd /tmp && tar xzf web.tgz
  rm -rf /var/www/golgerota-app && mv web /var/www/golgerota-app
  chown -R caddy:caddy /var/www/golgerota-app'
```

Caddy bloğu:

```
app.$API_SUBDOMAIN {
	root * /var/www/golgerota-app
	encode gzip
	try_files {path} /index.html
	file_server
}
```

`config.dart` varsayılan `API_BASE` canlı API'yi gösterdiği için düz
`flutter build web` yeterli.

## APK aynası (GitHub bazı bölgelerde yavaş)

Caddy `$API_SUBDOMAIN/dl/*` yolunu `/var/www/golgerota-dl/` klasöründen
statik sunuyor. Yeni sürüm APK'larını oraya koy:

```bash
# yerelden
scp golge-rota-vX-arm64.apk root@$SERVER_HOST:/var/www/golgerota-dl/
# ya da sunucuda GitHub'dan çek (sunucu→GitHub hızlı)
ssh root@$SERVER_HOST 'curl -sSL -o /var/www/golgerota-dl/x.apk <github-release-asset-url>'
ssh root@$SERVER_HOST 'chown caddy:caddy /var/www/golgerota-dl/*.apk'
```

Caddy bloğu:

```
$API_SUBDOMAIN {
	handle_path /dl/* {
		root * /var/www/golgerota-dl
		file_server browse
	}
	handle { reverse_proxy 127.0.0.1:$APP_PORT }
}
```
