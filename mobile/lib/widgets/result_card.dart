import 'package:flutter/material.dart';

import '../models/shadow_analysis.dart';
import 'route_sun_map.dart';
import 'seat_diagram.dart';

class ResultCard extends StatelessWidget {
  const ResultCard({super.key, required this.result});

  final ShadowAnalysis result;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${result.routeName} · ${result.directionLabel}',
                style: t.titleMedium),
            if (result.fromStop != null && result.toStop != null) ...[
              const SizedBox(height: 2),
              Row(
                children: [
                  const Icon(Icons.directions_walk, size: 15),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text('${result.fromStop} → ${result.toStop}',
                        style: t.bodySmall),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 2),
            Text(
              '${_hm(result.departure)} kalkış · ~${result.tripDurationMin.round()} dk · '
              '${result.totalLengthKm.toStringAsFixed(1)} km',
              style: t.bodySmall?.copyWith(color: Theme.of(context).hintColor),
            ),
            const SizedBox(height: 16),
            SeatDiagram(
              recommendedSide: result.recommendedSide,
              sunnySide: result.sunnySide,
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primaryContainer,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                result.headline,
                style: t.titleSmall?.copyWith(
                  color: Theme.of(context).colorScheme.onPrimaryContainer,
                ),
              ),
            ),
            const SizedBox(height: 16),
            _Breakdown(breakdown: result.breakdownPct),
            if (result.segments.length >= 2) ...[
              const SizedBox(height: 16),
              RouteSunMap(segments: result.segments),
            ],
            if (result.notes.isNotEmpty) ...[
              const SizedBox(height: 12),
              for (final n in result.notes)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('• '),
                      Expanded(child: Text(n, style: t.bodySmall)),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  static String _hm(DateTime d) =>
      '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
}

class _Breakdown extends StatelessWidget {
  const _Breakdown({required this.breakdown});

  final Map<SunSide, double> breakdown;

  static const _order = [
    SunSide.left,
    SunSide.right,
    SunSide.front,
    SunSide.back,
    SunSide.none,
  ];

  static const _colors = {
    SunSide.left: Color(0xFF5B8DEF),
    SunSide.right: Color(0xFFEF8A5B),
    SunSide.front: Color(0xFFE0C341),
    SunSide.back: Color(0xFF8D8D8D),
    SunSide.none: Color(0xFFB0B0B0),
  };

  static const _labels = {
    SunSide.left: 'Sol',
    SunSide.right: 'Sağ',
    SunSide.front: 'Ön cam',
    SunSide.back: 'Arka',
    SunSide.none: 'Tünel / güneş yok',
  };

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Güneş rotanın nesinde, nereden:', style: t.labelMedium),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: Row(
            children: [
              for (final s in _order)
                if ((breakdown[s] ?? 0) > 0.5)
                  Expanded(
                    flex: ((breakdown[s] ?? 0) * 10).round().clamp(1, 1000),
                    child: Container(height: 14, color: _colors[s]),
                  ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 4,
          children: [
            for (final s in _order)
              if ((breakdown[s] ?? 0) > 0.5)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(width: 10, height: 10, color: _colors[s]),
                    const SizedBox(width: 4),
                    Text('${_labels[s]} %${(breakdown[s] ?? 0).round()}',
                        style: t.bodySmall),
                  ],
                ),
          ],
        ),
      ],
    );
  }
}
