// kairos_mobile_app/lib/theme.dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// Centralized color palette for easy access and modification.
class AppColors {
  static const Color primaryColor = Color(0xFF4A90E2); // Blue accent
  static const Color secondaryColor = Color(0xFF50E3C2); // Teal/Green accent
  static const Color background = Color(0xFF252525); // Dark background
  static const Color surface = Color(0xFF2c2c2c); // Slightly lighter surface
  static const Color card =
      Color(0xFF333333); // Card and input field background
  static const Color textPrimary = Color(0xFFF0F0F0); // Bright primary text
  static const Color textSecondary = Color(0xFFAAAAAA); // Dimmer secondary text
  static const Color error = Color(0xFFD0021B); // Red for errors
}

// This function builds and returns the entire theme data for the app.
ThemeData buildAppTheme() {
  // Start with a base dark theme.
  final baseTheme = ThemeData.dark(useMaterial3: true);

  // Customize the base theme with our specific colors and fonts.
  return baseTheme.copyWith(
    primaryColor: AppColors.primaryColor,
    scaffoldBackgroundColor: AppColors.surface,
    colorScheme: baseTheme.colorScheme.copyWith(
      primary: AppColors.primaryColor,
      secondary: AppColors.secondaryColor,
      surface: AppColors.surface,
      error: AppColors.error,
      onPrimary: Colors.black, // Text on primary color buttons
      onSecondary: Colors.black,
      onSurface: AppColors.textPrimary,
    ),

    // Define the global font family using Google Fonts.
    // We use Poppins as a modern, clean choice.
    textTheme: GoogleFonts.poppinsTextTheme(baseTheme.textTheme).copyWith(
      // You can customize specific text styles here if needed.
      // For example, making headlines bolder:
      headlineSmall: GoogleFonts.poppins(
        fontWeight: FontWeight.bold,
        color: AppColors.textPrimary,
      ),
      bodyMedium: GoogleFonts.poppins(
        color: AppColors.textSecondary,
      ),
    ),

    // Customize the appearance of specific widgets.
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.background,
      foregroundColor: AppColors.textPrimary,
      centerTitle: true,
      elevation: 0,
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: AppColors.background,
      selectedItemColor: AppColors.secondaryColor,
      unselectedItemColor: AppColors.textSecondary,
    ),
    cardTheme: CardThemeData(
      color: AppColors.card,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        backgroundColor: AppColors.primaryColor,
        foregroundColor: Colors.black, // Text color on the button
      ),
    ),
  );
}
