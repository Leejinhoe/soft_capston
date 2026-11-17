import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Shared visual tokens for the app-integration dark violet UI.
class AppColors {
  static const pageBackground = Color(0xFF070018);
  static const pageSurface = Color(0xFF140028);
  static const pageInput = Color(0xFF1A0B3A);
  static const pageRaised = Color(0xFF1A0B3A);
  static const bg = pageBackground;
  static const bg2 = pageSurface;
  static const card = pageSurface;
  static const card2 = Color(0xFF1A0B3A);
  static const p700 = Color(0xFF5B21B6);
  static const p600 = Color(0xFF7C3AED);
  static const p500 = Color(0xFF8B5CF6);
  static const p400 = Color(0xFFA78BFA);
  static const p300 = Color(0xFFC4B5FD);
  static const pink = Color(0xFFEC4899);
  static const pink2 = Color(0xFFF472B6);
  static const teal = Color(0xFF14B8A6);
  static const gray = Color(0xFF9CA3AF);
  static const gray2 = Color(0xFF6B7280);
  static const border = Color(0x1AFFFFFF);
}

class AppTheme {
  const AppTheme._();

  static ThemeData get dark => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.pageBackground,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.p500,
      secondary: AppColors.pink,
      surface: AppColors.pageSurface,
      onPrimary: Colors.white,
      onSurface: Colors.white,
    ),
    textTheme: GoogleFonts.notoSansKrTextTheme(
      ThemeData.dark().textTheme,
    ).apply(bodyColor: Colors.white, displayColor: Colors.white),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.pageBackground,
      elevation: 0,
      centerTitle: true,
      scrolledUnderElevation: 0,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: TextStyle(
        color: Colors.white,
        fontSize: 18,
        fontWeight: FontWeight.w700,
      ),
      iconTheme: IconThemeData(color: Colors.white),
    ),
    cardTheme: CardThemeData(
      color: AppColors.pageSurface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.pageInput,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      hintStyle: const TextStyle(color: Colors.white38),
      labelStyle: const TextStyle(color: AppColors.p300),
      prefixIconColor: AppColors.p300,
      suffixIconColor: Colors.white54,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: AppColors.p400, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: Color(0xFFEF4444)),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: Color(0xFFEF4444), width: 1.5),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.p600,
        foregroundColor: Colors.white,
        disabledBackgroundColor: Colors.white12,
        disabledForegroundColor: Colors.white38,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 15),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.p600,
        foregroundColor: Colors.white,
        disabledBackgroundColor: Colors.white12,
        disabledForegroundColor: Colors.white38,
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 15),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.p300,
        side: const BorderSide(color: AppColors.border),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: AppColors.p300,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: AppColors.pageSurface,
      selectedColor: AppColors.p600,
      secondarySelectedColor: AppColors.p600,
      disabledColor: Colors.white10,
      side: const BorderSide(color: AppColors.border),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      labelStyle: const TextStyle(
        color: Colors.white70,
        fontWeight: FontWeight.w600,
      ),
      secondaryLabelStyle: const TextStyle(
        color: Colors.white,
        fontWeight: FontWeight.w700,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.pageSurface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(26)),
      titleTextStyle: const TextStyle(
        color: Colors.white,
        fontSize: 20,
        fontWeight: FontWeight.w700,
      ),
      contentTextStyle: const TextStyle(color: Colors.white70, height: 1.5),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.pageSurface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      showDragHandle: true,
      dragHandleColor: Colors.white24,
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: Colors.white,
      unselectedLabelColor: Colors.white60,
      indicatorColor: AppColors.p400,
      dividerColor: Colors.white10,
      labelStyle: TextStyle(fontWeight: FontWeight.w700),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.p400,
      linearTrackColor: Colors.white12,
      circularTrackColor: Colors.white12,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.pageRaised,
      contentTextStyle: const TextStyle(color: Colors.white),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    listTileTheme: const ListTileThemeData(
      iconColor: AppColors.p300,
      textColor: Colors.white,
      subtitleTextStyle: TextStyle(color: Colors.white60),
      selectedColor: AppColors.p300,
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: AppColors.pageSurface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      textStyle: const TextStyle(color: Colors.white),
    ),
    dividerTheme: const DividerThemeData(
      color: Colors.white12,
      thickness: 1,
      space: 1,
    ),
  );
}
