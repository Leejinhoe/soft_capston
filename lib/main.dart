import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'models/app_state.dart';
import 'screens/main_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  runApp(
    ChangeNotifierProvider(
      create: (_) => AppState(),
      child: const FairytaleApp(),
    ),
  );
}

// ─── 앱 색상 팔레트 (HTML 디자인 동일) ───
class AppColors {
  static const bg    = Color(0xFF06041A);
  static const bg2   = Color(0xFF0E0B28);
  static const card  = Color(0xFF160F38);
  static const card2 = Color(0xFF1E1645);
  static const p700  = Color(0xFF5B21B6);
  static const p600  = Color(0xFF7C3AED);
  static const p500  = Color(0xFF8B5CF6);
  static const p400  = Color(0xFFA78BFA);
  static const p300  = Color(0xFFC4B5FD);
  static const pink  = Color(0xFFEC4899);
  static const pink2 = Color(0xFFF472B6);
  static const teal  = Color(0xFF14B8A6);
  static const gray  = Color(0xFF9CA3AF);
  static const gray2 = Color(0xFF6B7280);
  static const border = Color(0x337C3AED);
}

class FairytaleApp extends StatelessWidget {
  const FairytaleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '동화 AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.bg,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.p500,
          secondary: AppColors.pink,
          surface: AppColors.card,
          onPrimary: Colors.white,
          onSurface: Colors.white,
        ),
        textTheme: GoogleFonts.notoSansKrTextTheme(ThemeData.dark().textTheme),
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.bg,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
          iconTheme: IconThemeData(color: Colors.white),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.p600,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 24),
          ),
        ),
      ),
      home: const MainShell(),
    );
  }
}
