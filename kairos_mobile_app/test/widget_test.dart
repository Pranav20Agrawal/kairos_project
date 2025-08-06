// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart'; // Import Material library
import 'package:flutter_test/flutter_test.dart';

import 'package:kairos_mobile_app/main.dart'; // Make sure this import is correct

void main() {
  testWidgets('App displays K.A.I.R.O.S. Mobile title', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const KairosMobileApp());

    // Verify that our app bar title is displayed.
    expect(find.text('K.A.I.R.O.S. Mobile'), findsOneWidget);

    // Verify the presence of bottom navigation bar labels
    expect(find.text('Dashboard'), findsOneWidget);
    expect(find.text('Transfer'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
  });
}