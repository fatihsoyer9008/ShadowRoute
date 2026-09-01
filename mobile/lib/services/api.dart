import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/route_summary.dart';
import '../models/shadow_analysis.dart';

/// Kullanıcıya gösterilebilir hata mesajı taşıyan istisna.
class ApiException implements Exception {
  final String message;
  const ApiException(this.message);
  @override
  String toString() => message;
}

class Api {
  Api({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  final Uri _base = Uri.parse(Config.apiBase);

  Future<List<RouteSummary>> routes() async {
    final data = await _getJson('/routes');
    if (data is! List) {
      throw const ApiException('Beklenmeyen sunucu cevabı (hat listesi).');
    }
    return data
        .map((e) => RouteSummary.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
  }

  /// Burulaş'ta hat arar. Boş liste = eşleşme yok.
  Future<List<RouteHit>> search(String query) async {
    final q = query.trim();
    if (q.isEmpty) return const [];
    final data = await _getJson('/search', query: {'q': q});
    if (data is! List) {
      throw const ApiException('Beklenmeyen sunucu cevabı (arama).');
    }
    return data
        .map((e) => RouteHit.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
  }

  /// Bir hattın yön/durak detayı (statik ya da `live-<hatNo>`).
  /// [direction] verilirse `stops` o yöndeki sıralı durak listesi olur.
  Future<RouteSummary> routeDetail(String id, {String? direction}) async {
    final data = await _getJson('/routes/$id',
        query: direction == null ? null : {'direction': direction});
    if (data is! Map) {
      throw const ApiException('Beklenmeyen sunucu cevabı (hat detayı).');
    }
    return RouteSummary.fromJson(data.cast<String, dynamic>());
  }

  Future<ShadowAnalysis> shadow(
    String routeId, {
    required String direction,
    DateTime? when,
    int? fromStop,
    int? toStop,
  }) async {
    final q = <String, String>{'direction': direction};
    if (fromStop != null) q['from'] = '$fromStop';
    if (toStop != null) q['to'] = '$toStop';
    if (when != null) {
      // Backend saat dilimsiz ISO'yu Türkiye saati (+03) kabul ediyor.
      final l = when.toLocal();
      q['when'] = '${l.year.toString().padLeft(4, '0')}-'
          '${l.month.toString().padLeft(2, '0')}-'
          '${l.day.toString().padLeft(2, '0')}T'
          '${l.hour.toString().padLeft(2, '0')}:'
          '${l.minute.toString().padLeft(2, '0')}';
    }
    final data = await _getJson('/routes/$routeId/shadow', query: q);
    if (data is! Map) {
      throw const ApiException('Beklenmeyen sunucu cevabı (analiz).');
    }
    return ShadowAnalysis.fromJson(data.cast<String, dynamic>());
  }

  Future<dynamic> _getJson(String path, {Map<String, String>? query}) async {
    final uri = _base.replace(
      path: '${_base.path}$path',
      queryParameters: query,
    );
    try {
      final res = await _client.get(uri).timeout(Config.httpTimeout);
      if (res.statusCode == 404) {
        throw const ApiException('İstenen hat bulunamadı.');
      }
      if (res.statusCode >= 500) {
        throw const ApiException('Sunucu şu an yanıt veremiyor. Sonra tekrar dene.');
      }
      if (res.statusCode != 200) {
        throw ApiException('İstek başarısız (HTTP ${res.statusCode}).');
      }
      return jsonDecode(utf8.decode(res.bodyBytes));
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException('Sunucu zaman aşımına uğradı. Bağlantını kontrol et.');
    } on SocketException {
      throw ApiException('Sunucuya ulaşılamadı ($_base). Backend çalışıyor mu?');
    } on FormatException {
      throw const ApiException('Sunucudan geçersiz veri geldi.');
    }
  }

  void close() => _client.close();
}
