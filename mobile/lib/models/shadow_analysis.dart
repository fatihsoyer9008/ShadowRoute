/// Güneşin otobüsün gidiş yönüne göre konumu.
enum SunSide { left, right, front, back, none }

SunSide sunSideFromString(String? s) {
  switch (s) {
    case 'left':
      return SunSide.left;
    case 'right':
      return SunSide.right;
    case 'front':
      return SunSide.front;
    case 'back':
      return SunSide.back;
    default:
      return SunSide.none;
  }
}

extension SunSideX on SunSide {
  String get tr => switch (this) {
        SunSide.left => 'sol',
        SunSide.right => 'sağ',
        SunSide.front => 'ön',
        SunSide.back => 'arka',
        SunSide.none => 'yok',
      };
}

/// Backend `GET /routes/{id}/shadow` çıktısı.
class ShadowAnalysis {
  final String routeName;
  final String directionLabel;
  final DateTime departure;
  final double tripDurationMin;
  final double totalLengthKm;
  final double sunUpFraction;
  final SunSide recommendedSide;
  final String headline;
  final List<String> notes;

  /// Rota uzunluğunun yüzdesi olarak taraf dağılımı (left/right/front/back/none).
  final Map<SunSide, double> breakdownPct;

  const ShadowAnalysis({
    required this.routeName,
    required this.directionLabel,
    required this.departure,
    required this.tripDurationMin,
    required this.totalLengthKm,
    required this.sunUpFraction,
    required this.recommendedSide,
    required this.headline,
    required this.notes,
    required this.breakdownPct,
  });

  factory ShadowAnalysis.fromJson(Map<String, dynamic> j) {
    final route = (j['route'] as Map?)?.cast<String, dynamic>() ?? const {};
    final bd = (j['breakdown_pct_of_route'] as Map?)?.cast<String, dynamic>() ??
        const {};
    double pct(String k) => (bd[k] as num?)?.toDouble() ?? 0.0;

    return ShadowAnalysis(
      routeName: (route['name'] as String?) ?? '',
      directionLabel: (route['direction_label'] as String?) ?? '',
      departure:
          DateTime.tryParse(j['departure'] as String? ?? '') ?? DateTime.now(),
      tripDurationMin: (j['trip_duration_min'] as num?)?.toDouble() ?? 0.0,
      totalLengthKm: (j['total_length_km'] as num?)?.toDouble() ?? 0.0,
      sunUpFraction: (j['sun_up_fraction'] as num?)?.toDouble() ?? 0.0,
      recommendedSide: sunSideFromString(j['recommended_side'] as String?),
      headline: (j['headline'] as String?) ?? '',
      notes: (j['notes'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      breakdownPct: {
        SunSide.left: pct('left'),
        SunSide.right: pct('right'),
        SunSide.front: pct('front'),
        SunSide.back: pct('back'),
        SunSide.none: pct('none'),
      },
    );
  }

  bool get hasSideRecommendation =>
      recommendedSide == SunSide.left || recommendedSide == SunSide.right;

  /// Öneriye göre güneşin geldiği (kaçılması gereken) taraf.
  SunSide get sunnySide => switch (recommendedSide) {
        SunSide.left => SunSide.right,
        SunSide.right => SunSide.left,
        _ => SunSide.none,
      };
}
