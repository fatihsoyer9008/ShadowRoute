/// Uygulama geneli ayarlar.
///
/// Varsayılan: Hetzner'daki canlı backend (HTTPS). Yerel geliştirme için:
///   flutter run --dart-define=API_BASE=http://localhost:8000          # web/masaüstü
///   flutter run --dart-define=API_BASE=http://10.0.2.2:8000           # Android emülatör
///   flutter build apk --dart-define=API_BASE=http://192.168.1.5:8000  # LAN'daki PC
class Config {
  static const String apiBase = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'https://golgerota.116-202-14-23.sslip.io',
  );

  static const Duration httpTimeout = Duration(seconds: 15);
}
