import 'package:flutter/material.dart';
import '../core/auth_service.dart';
import 'user_list_page.dart';
import 'report_list_page.dart';

class AdminPage extends StatelessWidget {
  const AdminPage({super.key});

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
              child: Icon(
                icon,
                color: Colors.white,
                size: 30,
              ),
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
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.arrow_forward_ios,
              color: Colors.white70,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),

      appBar: AppBar(
        backgroundColor: const Color(0xFF070018),
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "관리자 페이지",
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),

      body: SingleChildScrollView(
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
              style: TextStyle(
                color: Colors.white70,
                fontSize: 16,
              ),
            ),

            const SizedBox(height: 35),

            buildMenuCard(
              icon: Icons.people,
              title: "회원 관리",
              subtitle: "회원 조회 및 관리",
              colors: const [
                Color(0xFF8B5CF6),
                Color(0xFFEC4899),
              ],
              onTap: () {

                Navigator.push(

                  context,

                  MaterialPageRoute(

                    builder: (_) => const UserListPage(),
                  ),
                );
              },
            ),

            buildMenuCard(
              icon: Icons.report,
              title: "신고 관리",
              subtitle: "신고된 회원 및 게시글 관리",
              colors: const [
                Color(0xFFEF4444),
                Color(0xFFF97316),
              ],
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const ReportListPage(),
                  ),
                );
              },
            ),

            buildMenuCard(
              icon: Icons.menu_book,
              title: "동화 관리",
              subtitle: "생성된 동화 관리",
              colors: const [
                Color(0xFF3B82F6),
                Color(0xFF06B6D4),
              ],
              onTap: () {},
            ),

            buildMenuCard(
              icon: Icons.campaign,
              title: "공지사항",
              subtitle: "공지 등록 및 수정",
              colors: const [
                Color(0xFF10B981),
                Color(0xFF34D399),
              ],
              onTap: () {},
            ),

            const SizedBox(height: 40),

            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton.icon(
                onPressed: () {
                  AuthService.logout();
                },
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
    );
  }
}