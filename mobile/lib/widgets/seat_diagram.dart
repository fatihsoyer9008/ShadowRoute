import 'package:flutter/material.dart';

import '../models/shadow_analysis.dart';

/// Basit, şematik otobüs görünümü: iki koltuk sütunu (sol / sağ).
/// Önerilen taraf yeşil, güneş alan taraf turuncu vurgulanır.
class SeatDiagram extends StatelessWidget {
  const SeatDiagram({
    super.key,
    required this.recommendedSide,
    required this.sunnySide,
  });

  final SunSide recommendedSide;
  final SunSide sunnySide;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final w = c.maxWidth.clamp(0.0, 340.0);
        return Center(
          child: SizedBox(
            width: w,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _endLabel(context, Icons.airline_seat_recline_normal, 'ÖN'),
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: _sideColumn(context, SunSide.left, 'SOL')),
                    const SizedBox(width: 10),
                    Expanded(child: _sideColumn(context, SunSide.right, 'SAĞ')),
                  ],
                ),
                const SizedBox(height: 6),
                _endLabel(context, Icons.rectangle_outlined, 'ARKA'),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _endLabel(BuildContext context, IconData icon, String text) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 16, color: Theme.of(context).colorScheme.outline),
        const SizedBox(width: 6),
        Text(text,
            style: Theme.of(context)
                .textTheme
                .labelSmall
                ?.copyWith(letterSpacing: 2)),
      ],
    );
  }

  Widget _sideColumn(BuildContext context, SunSide side, String label) {
    final scheme = Theme.of(context).colorScheme;
    final isRecommended = side == recommendedSide;
    final isSunny = side == sunnySide;

    final Color bg;
    final Color border;
    if (isRecommended) {
      bg = Colors.green.withValues(alpha: 0.14);
      border = Colors.green;
    } else if (isSunny) {
      bg = Colors.orange.withValues(alpha: 0.16);
      border = Colors.orange;
    } else {
      bg = scheme.surfaceContainerHighest.withValues(alpha: 0.4);
      border = scheme.outlineVariant;
    }

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border, width: isRecommended || isSunny ? 2 : 1),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (isSunny)
                const Icon(Icons.wb_sunny, size: 16, color: Colors.orange),
              if (isRecommended)
                const Icon(Icons.check_circle, size: 16, color: Colors.green),
              const SizedBox(width: 4),
              Text(label,
                  style: Theme.of(context)
                      .textTheme
                      .labelMedium
                      ?.copyWith(fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 8),
          for (var i = 0; i < 5; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  _seat(border),
                  const SizedBox(width: 6),
                  _seat(border),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _seat(Color color) {
    return Expanded(
      child: Container(
        height: 22,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.25),
          borderRadius: BorderRadius.circular(5),
        ),
      ),
    );
  }
}
