/// Backend `GET /routes` çıktısındaki bir hat.
class RouteSummary {
  final String id;
  final String name;
  final String mode; // "bus" | "metro"
  final Map<String, String> directions; // "forward"/"backward" -> etiket
  final List<String> stops;

  const RouteSummary({
    required this.id,
    required this.name,
    required this.mode,
    required this.directions,
    required this.stops,
  });

  factory RouteSummary.fromJson(Map<String, dynamic> j) {
    final dir = (j['directions'] as Map?)?.cast<String, dynamic>() ?? const {};
    return RouteSummary(
      id: j['id'] as String,
      name: j['name'] as String,
      mode: (j['mode'] as String?) ?? 'bus',
      directions: dir.map((k, v) => MapEntry(k, v.toString())),
      stops: (j['stops'] as List?)?.map((e) => e.toString()).toList() ?? const [],
    );
  }

  bool get isMetro => mode == 'metro';
}
