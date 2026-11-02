import 'package:flutter/material.dart';
import '../core/api_client.dart';

class ReportDetailPage extends StatefulWidget {
  final Map<String, dynamic> report;

  const ReportDetailPage({
    super.key,
    required this.report,
  });

  @override
  State<ReportDetailPage> createState() => _ReportDetailPageState();
}

class _ReportDetailPageState extends State<ReportDetailPage> {

  // 작성자에게 경고를 부여하는 함수
  Future<void> giveWarning(String authorName) async {
    if (authorName.isEmpty || authorName == "알 수 없음") {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("작성자 정보가 없어 경고를 부여할 수 없습니다.")),
      );
      return;
    }

    try {
      final response = await ApiClient.put(
        "/admin/warning/${Uri.encodeComponent(authorName)}",
      );

      if (response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("'$authorName'님에게 경고 1회를 부여했습니다.")),
        );
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("회원 정보를 찾을 수 없거나 경고 처리에 실패했습니다.")),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("통신 오류가 발생했습니다: $e")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final report = widget.report;
    final String status = report["status"] ?? "waiting";

    return Scaffold(
      backgroundColor: const Color(0xFF070018),

      appBar: AppBar(
        backgroundColor: const Color(0xFF140028),
        foregroundColor: Colors.white,
        title: const Text(
          "신고 상세",
          style: TextStyle(
            fontWeight: FontWeight.bold,
          ),
        ),
      ),

      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            // 신고 상태
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF140028),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.report,
                    color: Color(0xFFEF4444),
                    size: 30,
                  ),

                  const SizedBox(width: 12),

                  const Expanded(
                    child: Text(
                      "신고 내용",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),

                  Text(
                    status == "waiting"
                        ? "처리 대기"
                        : "처리 완료",
                    style: TextStyle(
                      color: status == "waiting"
                          ? const Color(0xFFF97316)
                          : Colors.greenAccent,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 20),

            // 신고된 동화
            _buildInfoCard(
              title: "신고된 동화",
              icon: Icons.menu_book,
              child: Text(
                report["story_title"] ?? "제목 없음",
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),

            const SizedBox(height: 14),

            // 작성자
            _buildInfoCard(
              title: "작성자",
              icon: Icons.person,
              child: Text(
                report["author"] ?? "알 수 없음",
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                ),
              ),
            ),

            const SizedBox(height: 14),

            // 신고자
            _buildInfoCard(
              title: "신고자",
              icon: Icons.person_outline,
              child: Text(
                report["reporter"] ?? "알 수 없음",
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                ),
              ),
            ),

            const SizedBox(height: 14),

            // 신고 사유
            _buildInfoCard(
              title: "신고 사유",
              icon: Icons.warning_amber,
              child: Text(
                report["reason"] ?? "사유 없음",
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 16,
                ),
              ),
            ),

            const SizedBox(height: 14),

            // 신고 날짜
            _buildInfoCard(
              title: "신고 접수일",
              icon: Icons.calendar_today,
              child: Text(
                report["created_at"] ?? "",
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 14,
                ),
              ),
            ),

            const SizedBox(height: 14),

            // 신고 ID
            _buildInfoCard(
              title: "신고 ID",
              icon: Icons.tag,
              child: Text(
                report["id"] ?? "",
                style: const TextStyle(
                  color: Colors.white38,
                  fontSize: 13,
                ),
              ),
            ),

            const SizedBox(height: 30),

            // 1. 작성자에게 경고 버튼 (기능 연결 완료)
            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton.icon(
                onPressed: () {
                  final String author = report["author"] ?? "";
                  giveWarning(author);
                },
                icon: const Icon(Icons.warning_amber),
                label: const Text(
                  "작성자에게 경고",
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFF97316),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 12),

            // 2. 신고 처리 완료 버튼 (다음 단계 연결용)
            SizedBox(
              width: double.infinity,
              height: 55,
              child: OutlinedButton.icon(
                onPressed: () {
                  // 다음 단계인 '신고 처리 완료 (waiting -> completed)' API 연결 예정
                },
                icon: const Icon(Icons.check),
                label: const Text(
                  "신고 처리 완료",
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.greenAccent,
                  side: const BorderSide(
                    color: Colors.greenAccent,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoCard({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: Colors.white.withOpacity(0.08),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [

          Row(
            children: [
              Icon(
                icon,
                color: const Color(0xFF8B5CF6),
                size: 20,
              ),

              const SizedBox(width: 8),

              Text(
                title,
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          child,
        ],
      ),
    );
  }
}