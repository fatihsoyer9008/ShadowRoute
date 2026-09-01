import 'package:flutter/material.dart';

import '../models/route_summary.dart';
import '../models/shadow_analysis.dart';
import '../services/api.dart';
import '../widgets/result_card.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final Api _api = Api();

  late Future<List<RouteSummary>> _routesFuture;
  RouteSummary? _selected;
  String _direction = 'forward';
  DateTime? _when; // null => şimdi
  Future<ShadowAnalysis>? _resultFuture;

  @override
  void initState() {
    super.initState();
    _routesFuture = _api.routes();
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }

  void _reloadRoutes() {
    setState(() {
      _selected = null;
      _resultFuture = null;
      _routesFuture = _api.routes();
    });
  }

  Future<void> _pickTime() async {
    final now = DateTime.now();
    final base = _when ?? now;
    final date = await showDatePicker(
      context: context,
      initialDate: base,
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 7)),
      helpText: 'Yolculuk günü',
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(base),
      helpText: 'Yolculuk saati',
    );
    if (time == null) return;
    setState(() {
      _when = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    });
  }

  void _calculate() {
    final route = _selected;
    if (route == null) return;
    setState(() {
      _resultFuture = _api.shadow(
        route.id,
        direction: _direction,
        when: _when,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gölge Rota'),
        actions: [
          IconButton(
            onPressed: _reloadRoutes,
            icon: const Icon(Icons.refresh),
            tooltip: 'Hatları yenile',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _RoutesSection(
            future: _routesFuture,
            selected: _selected,
            onRetry: _reloadRoutes,
            onSelect: (r) => setState(() {
              _selected = r;
              _direction = r.directions.containsKey('forward')
                  ? 'forward'
                  : (r.directions.keys.isNotEmpty
                      ? r.directions.keys.first
                      : 'forward');
              _resultFuture = null;
            }),
          ),
          if (_selected != null) ...[
            const SizedBox(height: 20),
            Text('Yön', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: [
                for (final e in _selected!.directions.entries)
                  ButtonSegment(value: e.key, label: Text(e.value)),
              ],
              selected: {_direction},
              onSelectionChanged: (s) => setState(() {
                _direction = s.first;
                _resultFuture = null;
              }),
            ),
            const SizedBox(height: 20),
            Text('Ne zaman', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            Row(
              children: [
                ChoiceChip(
                  label: const Text('Şimdi'),
                  selected: _when == null,
                  onSelected: (_) => setState(() {
                    _when = null;
                    _resultFuture = null;
                  }),
                ),
                const SizedBox(width: 8),
                ActionChip(
                  avatar: const Icon(Icons.schedule, size: 18),
                  label: Text(_when == null ? 'Saat seç' : _fmt(_when!)),
                  onPressed: _pickTime,
                ),
              ],
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _calculate,
              icon: const Icon(Icons.wb_sunny_outlined),
              label: const Text('Gölge koltuğu bul'),
            ),
          ],
          const SizedBox(height: 24),
          if (_resultFuture != null) _ResultSection(future: _resultFuture!),
        ],
      ),
    );
  }

  static String _fmt(DateTime d) {
    final today = DateTime.now();
    final sameDay =
        d.year == today.year && d.month == today.month && d.day == today.day;
    final hm = '${d.hour.toString().padLeft(2, '0')}:'
        '${d.minute.toString().padLeft(2, '0')}';
    return sameDay ? 'Bugün $hm' : '${d.day}.${d.month} $hm';
  }
}

class _RoutesSection extends StatelessWidget {
  const _RoutesSection({
    required this.future,
    required this.selected,
    required this.onSelect,
    required this.onRetry,
  });

  final Future<List<RouteSummary>> future;
  final RouteSummary? selected;
  final ValueChanged<RouteSummary> onSelect;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<RouteSummary>>(
      future: future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError) {
          return _ErrorBox(message: snap.error.toString(), onRetry: onRetry);
        }
        final routes = snap.data ?? const [];
        if (routes.isEmpty) {
          return const _ErrorBox(message: 'Tanımlı hat yok.');
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Hat', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            DropdownButtonFormField<RouteSummary>(
              initialValue: selected,
              isExpanded: true,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: 'Bir hat seç',
              ),
              items: [
                for (final r in routes)
                  DropdownMenuItem(
                    value: r,
                    child: Text(r.name, overflow: TextOverflow.ellipsis),
                  ),
              ],
              onChanged: (r) {
                if (r != null) onSelect(r);
              },
            ),
          ],
        );
      },
    );
  }
}

class _ResultSection extends StatelessWidget {
  const _ResultSection({required this.future});

  final Future<ShadowAnalysis> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ShadowAnalysis>(
      future: future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 32),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError) {
          return _ErrorBox(message: snap.error.toString());
        }
        return ResultCard(result: snap.data!);
      },
    );
  }
}

class _ErrorBox extends StatelessWidget {
  const _ErrorBox({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.error_outline),
                const SizedBox(width: 8),
                Expanded(child: Text(message)),
              ],
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: onRetry,
                  child: const Text('Tekrar dene'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
