import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:golge_rota/main.dart';

void main() {
  testWidgets('açılışta başlık ve hat seçimi görünür', (tester) async {
    await tester.pumpWidget(const GolgeRotaApp());
    expect(find.text('Gölge Rota'), findsOneWidget);
    // Hat listesi ağdan gelene kadar yükleniyor göstergesi.
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
