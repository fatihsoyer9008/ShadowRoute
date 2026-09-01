/// Backend `GET /routes` veya `GET /routes/{id}` çıktısındaki bir hat.
class RouteSummary {
  final String id;
  final String name;
  final String mode; // "bus" | "metro"
  final Map<String, String> directions; // "forward"/"backward" -> etiket
  final List<String> stops;
  final bool isLoop;

  const RouteSummary({
    required this.id,
    required this.name,
    required this.mode,
    required this.directions,
    required this.stops,
    this.isLoop = false,
  });

  factory RouteSummary.fromJson(Map<String, dynamic> j) {
    final dir = (j['directions'] as Map?)?.cast<String, dynamic>() ?? const {};
    return RouteSummary(
      id: j['id'] as String,
      name: j['name'] as String,
      mode: (j['mode'] as String?) ?? 'bus',
      directions: dir.map((k, v) => MapEntry(k, v.toString())),
      stops: (j['stops'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      isLoop: j['is_loop'] == true,
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
