import 'package:flutter/material.dart';

import '../models/route_summary.dart';
import '../models/shadow_analysis.dart';
import '../services/api.dart';
import '../widgets/result_card.dart';
import 'search_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final Api _api = Api();

  List<RouteSummary> _curated = const [];
  String? _curatedError;

  RouteSummary? _selected;
  bool _loadingDetail = false;
  DateTime? _when; // null => şimdi
  Future<ShadowAnalysis>? _resultFuture;

  // Duraktan durağa (yön, seçilen durak sırasından çıkar)
  List<String> _stops = const [];
  int _fromIdx = 0;
  int _toIdx = 0;

  @override
  void initState() {
    super.initState();
    _loadCurated();
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }

  Future<void> _loadCurated() async {
    setState(() => _curatedError = null);
    try {
      final routes = await _api.routes();
      if (mounted) setState(() => _curated = routes);
    } catch (e) {
      if (mounted) setState(() => _curatedError = e.toString());
    }
  }

  Future<void> _openSearch() async {
    final id = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => SearchScreen(api: _api, curated: _curated),
      ),
    );
    if (id == null || !mounted) return;

    // Zaten elimizdeki hazır hat mı?
    final known = _curated.where((r) => r.id == id).toList();
    if (known.isNotEmpty) {
      _select(known.first);
      return;
    }

    setState(() {
      _loadingDetail = true;
      _selected = null;
      _resultFuture = null;
    });
    try {
      final detail = await _api.routeDetail(id);
      if (mounted) _select(detail);
    } catch (e) {
      if (mounted) {
        setState(() => _loadingDetail = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Hat yüklenemedi: $e')),
        );
      }
    }
  }

  void _select(RouteSummary r) {
    setState(() {
      _loadingDetail = false;
      _selected = r;
      _stops = r.stops;
      _fromIdx = r.defaultFrom.clamp(0, r.stops.isEmpty ? 0 : r.stops.length - 1);
      _toIdx = r.defaultTo.clamp(0, r.stops.isEmpty ? 0 : r.stops.length - 1);
      _resultFuture = null;
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
        when: _when,
        fromStop: _stops.length < 2 ? null : _fromIdx,
        toStop: _stops.length < 2 ? null : _toIdx,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Gölge Rota')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Hat', style: t.labelLarge),
          const SizedBox(height: 8),
          _RoutePickerField(
            selected: _selected,
            loading: _loadingDetail,
            onTap: _openSearch,
          ),
          if (_curatedError != null) ...[
            const SizedBox(height: 8),
            _ErrorBox(message: _curatedError!, onRetry: _loadCurated),
          ],
          if (_selected != null) ...[
            if (_stops.length >= 2) ...[
              const SizedBox(height: 20),
              Text('Nereden nereye', style: t.labelLarge),
              const SizedBox(height: 8),
              _StopPicker(
                stops: _stops,
                fromIdx: _fromIdx,
                toIdx: _toIdx,
                isLoop: _selected!.isLoop,
                onChanged: (from, to) => setState(() {
                  _fromIdx = from;
                  _toIdx = to;
                  _resultFuture = null;
                }),
              ),
            ],
            const SizedBox(height: 20),
            Text('Ne zaman', style: t.labelLarge),
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

class _StopPicker extends StatelessWidget {
  const _StopPicker({
    required this.stops,
    required this.fromIdx,
    required this.toIdx,
    required this.isLoop,
    required this.onChanged,
  });

  final List<String> stops;
  final int fromIdx;
  final int toIdx;
  final bool isLoop;
  final void Function(int from, int to) onChanged;

  @override
  Widget build(BuildContext context) {
    // Yön yok: "Nereden" ile "Nereye" farklı olsun yeter, sıra önemli değil.
    int otherIfEqual(int v, int other) {
      if (v != other) return other;
      return v < stops.length - 1 ? v + 1 : v - 1;
    }

    return Column(
      children: [
        _dropdown(context, 'Nereden', fromIdx,
            (v) => onChanged(v, otherIfEqual(v, toIdx))),
        const SizedBox(height: 8),
        _dropdown(context, 'Nereye', toIdx,
            (v) => onChanged(otherIfEqual(v, fromIdx), v)),
        if (!isLoop && !(fromIdx == 0 && toIdx == stops.length - 1))
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () => onChanged(0, stops.length - 1),
              child: const Text('Tüm hat'),
            ),
          ),
      ],
    );
  }

  Widget _dropdown(
      BuildContext context, String label, int value, ValueChanged<int> onSel) {
    return DropdownButtonFormField<int>(
      initialValue: value,
      isExpanded: true,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        isDense: true,
      ),
      items: [
        for (var i = 0; i < stops.length; i++)
          DropdownMenuItem(
            value: i,
            child: Text('${i + 1}. ${stops[i]}',
                overflow: TextOverflow.ellipsis),
          ),
      ],
      onChanged: (v) {
        if (v != null) onSel(v);
      },
    );
  }
}

class _RoutePickerField extends StatelessWidget {
  const _RoutePickerField({
    required this.selected,
    required this.loading,
    required this.onTap,
  });

  final RouteSummary? selected;
  final bool loading;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: loading ? null : onTap,
      borderRadius: BorderRadius.circular(8),
      child: InputDecorator(
        decoration: const InputDecoration(border: OutlineInputBorder()),
        child: Row(
          children: [
            if (loading)
              const SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(selected == null
                  ? Icons.search
                  : (selected!.isMetro
                      ? Icons.directions_subway
                      : Icons.directions_bus)),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                loading
                    ? 'Hat yükleniyor…'
                    : (selected?.name ?? 'Hat ara veya seç'),
                overflow: TextOverflow.ellipsis,
                style: selected == null
                    ? TextStyle(color: Theme.of(context).hintColor)
                    : null,
              ),
            ),
            if (selected != null && !loading)
              const Icon(Icons.edit, size: 18),
          ],
        ),
      ),
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
