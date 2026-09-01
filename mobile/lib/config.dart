/// Uygulama geneli ayarlar.
///
/// API adresini derleme sırasında değiştir:
///   flutter run --dart-define=API_BASE=http://192.168.1.20:8000
///
/// Varsayılan `10.0.2.2`, Android emülatöründen host makinesine (localhost)
/// erişmenin yoludur. Web/masaüstünde `http://localhost:8000` kullan.
class Config {
  static const String apiBase = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const Duration httpTimeout = Duration(seconds: 12);
}
