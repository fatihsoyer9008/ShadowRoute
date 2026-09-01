import 'dart:async';

import 'package:flutter/material.dart';

import '../models/route_summary.dart';
import '../services/api.dart';

/// Hat arama ekranı. Seçilen hattın id'sini `Navigator.pop` ile döndürür.
class SearchScreen extends StatefulWidget {
  const SearchScreen({
    super.key,
    required this.api,
    required this.curated,
  });

  final Api api;
  final List<RouteSummary> curated;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  String _query = '';
  Future<List<RouteHit>>? _results;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      final q = value.trim();
      setState(() {
        _query = q;
        _results = q.isEmpty ? null : widget.api.search(q);
      });
    });
  }

  void _pick(String id) => Navigator.of(context).pop(id);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _controller,
          autofocus: true,
          textInputAction: TextInputAction.search,
          onChanged: _onChanged,
          decoration: const InputDecoration(
            hintText: 'Hat no ya da adı (ör. 38, 96, M1)',
            border: InputBorder.none,
          ),
        ),
        actions: [
          if (_query.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.clear),
              onPressed: () {
                _controller.clear();
                _onChanged('');
              },
            ),
        ],
      ),
      body: _query.isEmpty ? _curatedList() : _searchResults(),
    );
  }

  Widget _curatedList() {
    return ListView(
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Text('Hazır hatlar (tünel bölgeleri ayarlı)'),
        ),
        for (final r in widget.curated)
          ListTile(
            leading: Icon(r.isMetro ? Icons.directions_subway : Icons.directions_bus),
            title: Text(r.name),
            subtitle: r.isLoop ? const Text('halka hat') : null,
            onTap: () => _pick(r.id),
          ),
      ],
    );
  }

  Widget _searchResults() {
    return FutureBuilder<List<RouteHit>>(
      future: _results,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: Padding(
            padding: EdgeInsets.all(32),
            child: CircularProgressIndicator(),
          ));
        }
        if (snap.hasError) {
          return _centered(
            Icons.error_outline,
            snap.error.toString(),
          );
        }
        final hits = snap.data ?? const [];
        if (hits.isEmpty) {
          return _centered(
            Icons.search_off,
            '"$_query" için hat bulunamadı.\nHat numarasını dene (ör. 38).',
          );
        }
        return ListView.builder(
          itemCount: hits.length,
          itemBuilder: (context, i) {
            final h = hits[i];
            return ListTile(
              leading: Icon(
                  h.isMetro ? Icons.directions_subway : Icons.directions_bus),
              title: Text(h.name),
              subtitle: Text(h.isMetro ? 'metro' : 'otobüs'),
              onTap: () => _pick(h.id),
            );
          },
        );
      },
    );
  }

  Widget _centered(IconData icon, String text) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: Theme.of(context).hintColor),
            const SizedBox(height: 12),
            Text(text, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
