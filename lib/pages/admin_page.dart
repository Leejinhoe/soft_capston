import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';
import '../core/auth_service.dart';
import 'notice_admin_page.dart';
import 'report_list_page.dart';
import 'story_admin_list_page.dart';
import 'user_list_page.dart';

/// 관리자 메인: 요약 숫자 + 메뉴 4개 (회원 / 신고 / 동화 / 공지)
class AdminPage extends StatefulWidget {
  const AdminPage({super.key});

  @override
  State<AdminPage> createState() => _AdminPageState();
}

class _AdminPageState extends State<AdminPage> {
  Map<String, dynamic>? summary;

  @override
  void initState() {
    super.initState();
    loadSummary();
  }

  Future<void> loadSummary() async {
    try {
      final response = await ApiClient.get('/api/admin/summary');
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() => summary = Map<String, dynamic>.from(ApiClient.decode(response)));
      }
    } catch (e) {
      debugPrint('관리자 요약 불러오기 오류: $e');
    }
  }

  // 다른 화면에서 돌아오면 요약 숫자를 새로 읽습니다.
  Future<void> _open(Widget page) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => page));
    loadSummary();
  }

  Widget buildMenuCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required List<Color> colors,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 18),
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: colors),
          borderRadius: BorderRadius.circular(28),
          boxShadow: [
            BoxShadow(
              color: colors.first.withOpacity(0.3),
              blurRadius: 18,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 62,
              height: 62,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.15),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(icon, color: Colors.white, size: 30),
            ),
            const SizedBox(width: 18),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    subtitle,
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white70),
          ],
        ),
      ),
    );
  }

  Widget _stat(String label, String key, IconData icon, Color color) {
    final value = summary?[key];
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 10),
        decoration: BoxDecoration(
          color: AdminColors.card,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withOpacity(0.35)),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 8),
            Text(
              value == null ? '-' : '$value',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 26,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white60, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pending = summary?['pending_reports'] ?? 0;
    return Scaffold(
      backgroundColor: AdminColors.bg,
      appBar: AppBar(
        backgroundColor: AdminColors.bg,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "관리자 페이지",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        actions: [
          IconButton(
            tooltip: '새로고침',
            icon: const Icon(Icons.refresh),
            onPressed: loadSummary,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: loadSummary,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "👋 관리자님 환영합니다.",
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                "AI Fairy Tale 관리 시스템",
                style: TextStyle(color: Colors.white70, fontSize: 16),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  _stat('전체 회원', 'total_users', Icons.people, AdminColors.purple),
                  const SizedBox(width: 10),
                  _stat('처리 대기 신고', 'pending_reports', Icons.report, AdminColors.orange),
                  const SizedBox(width: 10),
                  _stat('오늘 생성된 동화', 'today_stories', Icons.auto_stories, AdminColors.blue),
                ],
              ),
              const SizedBox(height: 28),
              buildMenuCard(
                icon: Icons.people,
                title: "회원 관리",
                subtitle: "회원 조회 · 경고 · 정지 · 탈퇴",
                colors: const [AdminColors.purple, AdminColors.pink],
                onTap: () => _open(const UserListPage()),
              ),
              buildMenuCard(
                icon: Icons.report,
                title: "신고 관리",
                subtitle: pending > 0 ? "처리 대기 $pending건" : "신고된 회원 및 게시글 관리",
                colors: const [AdminColors.red, AdminColors.orange],
                onTap: () => _open(const ReportListPage()),
              ),
              buildMenuCard(
                icon: Icons.menu_book,
                title: "동화 관리",
                subtitle: "모든 회원의 동화 조회 · 삭제",
                colors: const [AdminColors.blue, Color(0xFF06B6D4)],
                onTap: () => _open(const StoryAdminListPage()),
              ),
              buildMenuCard(
                icon: Icons.campaign,
                title: "공지사항",
                subtitle: "공지 등록 · 수정 · 삭제",
                colors: const [AdminColors.green, Color(0xFF34D399)],
                onTap: () => _open(const NoticeAdminPage()),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 55,
                child: ElevatedButton.icon(
                  onPressed: () => AuthService.logout(),
                  icon: const Icon(Icons.logout),
                  label: const Text("로그아웃"),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.redAccent,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
