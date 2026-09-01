import 'package:flutter_test/flutter_test.dart';

import 'package:golge_rota/main.dart';

void main() {
  testWidgets('açılışta başlık ve hat arama alanı görünür', (tester) async {
    await tester.pumpWidget(const GolgeRotaApp());
    expect(find.text('Gölge Rota'), findsOneWidget);
    expect(find.text('Hat ara veya seç'), findsOneWidget);
  });
}
