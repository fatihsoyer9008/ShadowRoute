import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/shadow_analysis.dart';

/// Rotanın şematik çizimi (alt harita yok) — her parça güneşin geldiği tarafa
/// göre renklendirilir. Kullanıcı yolun neresinde güneşe maruz kaldığını görür.
class RouteSunMap extends StatelessWidget {
  const RouteSunMap({super.key, required this.segments});

  final List<RouteSegment> segments;

  static const _colors = {
    SunSide.left: Color(0xFF5B8DEF),
    SunSide.right: Color(0xFFEF8A5B),
    SunSide.front: Color(0xFFE0C341),
    SunSide.back: Color(0xFF8D8D8D),
    SunSide.none: Color(0xFFB0B0B0),
  };
  static const _labels = {
    SunSide.left: 'sol',
    SunSide.right: 'sağ',
    SunSide.front: 'ön cam',
    SunSide.back: 'arka',
    SunSide.none: 'tünel / güneş yok',
  };

  /// Rotanın coğrafi en-boy oranı (mesafe düzeltmeli), makul aralığa kısıtlı.
  double _aspect() {
    double minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
    for (final s in segments) {
      minLat = math.min(minLat, s.lat);
      maxLat = math.max(maxLat, s.lat);
      minLon = math.min(minLon, s.lon);
      maxLon = math.max(maxLon, s.lon);
    }
    final kx = math.cos((minLat + maxLat) / 2 * math.pi / 180);
    final w = (maxLon - minLon).abs() * kx;
    final h = (maxLat - minLat).abs();
    if (h < 1e-9) return 3.0;
    return (w / h).clamp(0.62, 2.6);
  }

  @override
  Widget build(BuildContext context) {
    if (segments.length < 2) return const SizedBox.shrink();
    final present = <SunSide>{for (final s in segments) s.side};
    final t = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Rota boyunca güneş', style: t.labelMedium),
        const SizedBox(height: 8),
        AspectRatio(
          aspectRatio: _aspect(),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest
                  .withValues(alpha: 0.35),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: CustomPaint(
                painter: _RoutePainter(
                  segments,
                  _colors,
                  Theme.of(context).colorScheme.onSurface,
                ),
                size: Size.infinite,
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 4,
          children: [
            for (final s in _colors.keys)
              if (present.contains(s))
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(width: 10, height: 10, color: _colors[s]),
                  const SizedBox(width: 4),
                  Text(_labels[s]!, style: t.bodySmall),
                ]),
            Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.circle, size: 10, color: Theme.of(context).hintColor),
              const SizedBox(width: 4),
              Text('başlangıç', style: t.bodySmall),
            ]),
          ],
        ),
      ],
    );
  }
}

class _RoutePainter extends CustomPainter {
  _RoutePainter(this.segments, this.colors, this.startColor);

  final List<RouteSegment> segments;
  final Map<SunSide, Color> colors;
  final Color startColor;

  @override
  void paint(Canvas canvas, Size size) {
    double minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
    for (final s in segments) {
      minLat = math.min(minLat, s.lat);
      maxLat = math.max(maxLat, s.lat);
      minLon = math.min(minLon, s.lon);
      maxLon = math.max(maxLon, s.lon);
    }
    final midLat = (minLat + maxLat) / 2;
    final kx = math.cos(midLat * math.pi / 180); // boylamı mesafeye ölçekle
    final spanX = math.max((maxLon - minLon) * kx, 1e-6);
    final spanY = math.max(maxLat - minLat, 1e-6);
    final scale = math.min(size.width / spanX, size.height / spanY);
    final offX = (size.width - spanX * scale) / 2;
    final offY = (size.height - spanY * scale) / 2;

    Offset project(RouteSegment s) => Offset(
          offX + (s.lon - minLon) * kx * scale,
          // lat yukarı artar -> y'yi ters çevir
          size.height - offY - (s.lat - minLat) * scale,
        );

    final paint = Paint()
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    for (var i = 0; i < segments.length - 1; i++) {
      paint.color = colors[segments[i].side] ?? colors[SunSide.none]!;
      canvas.drawLine(project(segments[i]), project(segments[i + 1]), paint);
    }

    final start = project(segments.first);
    canvas.drawCircle(start, 5, Paint()..color = startColor);
    canvas.drawCircle(
        start, 5, Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5);
  }

  @override
  bool shouldRepaint(_RoutePainter old) => old.segments != segments;
}
