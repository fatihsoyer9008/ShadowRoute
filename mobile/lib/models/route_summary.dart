/// Backend `GET /routes` veya `GET /routes/{id}` çıktısındaki bir hat.
/// Duraklar yolculuk sırasıyla; yön, seçilen biniş/iniş sırasından çıkar.
class RouteSummary {
  final String id;
  final String name;
  final String mode; // "bus" | "metro"
  final List<String> stops;
  final bool isLoop;
  final int defaultFrom;
  final int defaultTo;

  const RouteSummary({
    required this.id,
    required this.name,
    required this.mode,
    required this.stops,
    this.isLoop = false,
    this.defaultFrom = 0,
    this.defaultTo = 0,
  });

  factory RouteSummary.fromJson(Map<String, dynamic> j) {
    final stops =
        (j['stops'] as List?)?.map((e) => e.toString()).toList() ?? const [];
    return RouteSummary(
      id: j['id'] as String,
      name: j['name'] as String,
      mode: (j['mode'] as String?) ?? 'bus',
      stops: stops,
      isLoop: j['is_loop'] == true,
      defaultFrom: (j['default_from'] as num?)?.toInt() ?? 0,
      defaultTo: (j['default_to'] as num?)?.toInt() ??
          (stops.isEmpty ? 0 : stops.length - 1),
    );
  }

  bool get isMetro => mode == 'metro';
}

/// `GET /search` sonucundaki hafif kayıt (yön/durak yok — seçilince detay çekilir).
class RouteHit {
  final String id;
  final String code;
  final String name;
  final String mode;

  const RouteHit({
    required this.id,
    required this.code,
    required this.name,
    required this.mode,
  });

  factory RouteHit.fromJson(Map<String, dynamic> j) => RouteHit(
        id: j['id'] as String,
        code: (j['code'] ?? j['name'] ?? '').toString(),
        name: (j['name'] ?? j['code'] ?? '').toString(),
        mode: (j['mode'] as String?) ?? 'bus',
      );

  bool get isMetro => mode == 'metro';
}
