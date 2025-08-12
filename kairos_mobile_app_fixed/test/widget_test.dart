// test/widget_test.dart

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// --- FIXED: Changed the import to your actual app ---
import 'package:kairos_mobile_app/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    // --- FIXED: Changed MyApp() to KairosMobileApp() ---
    await tester.pumpWidget(const KairosMobileApp());

    // Verify that the app bar title is present.
    expect(find.text('K.A.I.R.O.S. Mobile'), findsOneWidget);

    // Verify that the Dashboard icon is present.
    expect(find.byIcon(Icons.dashboard_rounded), findsOneWidget);
  });
}
