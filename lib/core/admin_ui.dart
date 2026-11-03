import 'package:flutter/material.dart';

import 'api_client.dart';

/// 관리자 화면 공통 색/위젯 (다크 + 보라색, 신고 관리 화면과 같은 톤)
class AdminColors {
  static const bg = Color(0xFF070018);
  static const card = Color(0xFF140028);
  static const purple = Color(0xFF8B5CF6);
  static const pink = Color(0xFFEC4899);
  static const orange = Color(0xFFF97316);
  static const red = Color(0xFFEF4444);
  static const blue = Color(0xFF3B82F6);
  static const green = Color(0xFF10B981);
}

PreferredSizeWidget adminAppBar(String title, {List<Widget>? actions}) {
  return AppBar(
    backgroundColor: AdminColors.card,
    foregroundColor: Colors.white,
    title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
    actions: actions,
  );
}

/// 서버의 UTC 시각(타임존 표시 없음) → 한국 시간 "2026.11.03 14:05"
String adminDate(dynamic iso, {bool withTime = true}) {
  final d = DateTime.tryParse((iso ?? '').toString());
  if (d == null) return '-';
  final utc = d.isUtc
      ? d
      : DateTime.utc(d.year, d.month, d.day, d.hour, d.minute, d.second);
  final l = utc.toLocal();
  String two(int v) => v.toString().padLeft(2, '0');
  final date = '${l.year}.${two(l.month)}.${two(l.day)}';
  return withTime ? '$date ${two(l.hour)}:${two(l.minute)}' : date;
}

void adminToast(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}

/// 실패 응답이면 서버 안내 문구를 띄우고 false
bool adminOk(BuildContext context, dynamic response) {
  if (response.statusCode == 200) return true;
  if (context.mounted) adminToast(context, ApiClient.errorMessage(response));
  return false;
}

Widget adminTag(String text, Color color) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    decoration: BoxDecoration(
      color: color.withOpacity(0.15),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Text(text,
        style:
            TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
  );
}

Widget adminChip({
  required String label,
  required bool selected,
  required VoidCallback onTap,
}) {
  return Padding(
    padding: const EdgeInsets.only(right: 8),
    child: ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AdminColors.purple,
      backgroundColor: AdminColors.card,
      showCheckmark: false,
      labelStyle: TextStyle(
        color: selected ? Colors.white : Colors.white70,
        fontWeight: FontWeight.bold,
      ),
      side: BorderSide(color: selected ? AdminColors.purple : Colors.white24),
    ),
  );
}

/// 검색창 (엔터나 돋보기 버튼으로 검색)
class AdminSearchField extends StatelessWidget {
  final TextEditingController controller;
  final String hint;
  final VoidCallback onSearch;

  const AdminSearchField({
    super.key,
    required this.controller,
    required this.hint,
    required this.onSearch,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white),
      textInputAction: TextInputAction.search,
      onSubmitted: (_) => onSearch(),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white38),
        filled: true,
        fillColor: AdminColors.card,
        isDense: true,
        prefixIcon: const Icon(Icons.search, color: Colors.white54),
        suffixIcon: IconButton(
          icon: const Icon(Icons.close, color: Colors.white38, size: 18),
          onPressed: () {
            controller.clear();
            onSearch();
          },
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Colors.white12),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Colors.white12),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AdminColors.purple),
        ),
      ),
    );
  }
}

/// 다크 테마 입력칸 스타일 (다이얼로그·공지 작성)
InputDecoration adminInputDecoration(String hint) {
  return InputDecoration(
    hintText: hint,
    hintStyle: const TextStyle(color: Colors.white38),
    filled: true,
    fillColor: AdminColors.bg,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Colors.white12),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Colors.white12),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: AdminColors.purple),
    ),
  );
}

/// 예/아니요 확인 팝업 (다크 테마)
Future<bool> adminConfirm(
  BuildContext context, {
  required String title,
  required String message,
  String okText = '확인',
  Color okColor = AdminColors.purple,
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: AdminColors.card,
      title: Text(title,
          style: const TextStyle(
              color: Colors.white, fontWeight: FontWeight.bold)),
      content: Text(message,
          style: const TextStyle(color: Colors.white70, height: 1.5)),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('취소', style: TextStyle(color: Colors.white54)),
        ),
        ElevatedButton(
          onPressed: () => Navigator.pop(ctx, true),
          style: ElevatedButton.styleFrom(
              backgroundColor: okColor, foregroundColor: Colors.white),
          child: Text(okText),
        ),
      ],
    ),
  );
  return result == true;
}

/// 목록 아래 "더보기" 버튼
Widget adminLoadMore({required bool loading, required VoidCallback onTap}) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Center(
      child: loading
          ? const CircularProgressIndicator(color: AdminColors.purple)
          : OutlinedButton(
              onPressed: onTap,
              style: OutlinedButton.styleFrom(
                foregroundColor: AdminColors.purple,
                side: const BorderSide(color: AdminColors.purple),
              ),
              child: const Text('더보기'),
            ),
    ),
  );
}

const adminLoading =
    Center(child: CircularProgressIndicator(color: AdminColors.purple));

Widget adminEmpty(String text) => Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Text(text,
            style: const TextStyle(color: Colors.white70, fontSize: 16)),
      ),
    );
