import 'package:flutter/material.dart';
import '../core/api_client.dart';
import 'report_detail_page.dart';

/// 신고 상태 → 화면 문구/색 (목록·상세 공통)
const reportStatusLabels = {
  'pending': '처리 대기',
  'resolved': '처리 완료',
  'rejected': '반려',
};

Color reportStatusColor(String status) {
  switch (status) {
    case 'resolved':
      return Colors.greenAccent;
    case 'rejected':
      return Colors.white54;
    default:
      return const Color(0xFFF97316);
  }
}

/// 관리자 > 신고 관리 (GET /api/admin/reports)
class ReportListPage extends StatefulWidget {
  const ReportListPage({super.key});

  @override
  State<ReportListPage> createState() => _ReportListPageState();
}

class _ReportListPageState extends State<ReportListPage> {
  static const _filters = [
    ('', '전체'),
    ('pending', '처리 대기'),
    ('resolved', '처리 완료'),
    ('rejected', '반려'),
  ];

  List<Map<String, dynamic>> reports = [];
  bool isLoading = true;
  String status = 'pending';
  int pendingCount = 0;

  @override
  void initState() {
    super.initState();
    fetchReports();
  }

  Future<void> fetchReports() async {
    setState(() => isLoading = true);
    try {
      final query = status.isEmpty ? '' : '&status=$status';
      final response = await ApiClient.get("/api/admin/reports?size=100$query");

      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          reports = (data['items'] as List).cast<Map<String, dynamic>>();
          pendingCount = data['pending_count'] ?? 0;
          isLoading = false;
        });
      } else {
        setState(() => isLoading = false);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => isLoading = false);
      debugPrint("신고 목록 불러오기 오류: $e");
    }
  }

  Future<void> _openDetail(Map<String, dynamic> report) async {
    final changed = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => ReportDetailPage(report: report)),
    );
    if (changed == true) fetchReports();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF140028),
        foregroundColor: Colors.white,
        title: Text(
          pendingCount > 0 ? "신고 관리 (대기 $pendingCount)" : "신고 관리",
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(
              children: _filters.map((f) {
                final selected = status == f.$1;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(f.$2),
                    selected: selected,
                    onSelected: (_) {
                      setState(() => status = f.$1);
                      fetchReports();
                    },
                    selectedColor: const Color(0xFF8B5CF6),
                    backgroundColor: const Color(0xFF140028),
                    labelStyle: TextStyle(
                      color: selected ? Colors.white : Colors.white70,
                      fontWeight: FontWeight.bold,
                    ),
                    side: BorderSide(
                      color: selected ? const Color(0xFF8B5CF6) : Colors.white24,
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          Expanded(child: _list()),
        ],
      ),
    );
  }

  Widget _list() {
    if (isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: Color(0xFF8B5CF6)),
      );
    }
    if (reports.isEmpty) {
      return const Center(
        child: Text(
          "접수된 신고가 없습니다.",
          style: TextStyle(color: Colors.white70, fontSize: 16),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: fetchReports,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: reports.length,
        itemBuilder: (context, index) => _card(reports[index]),
      ),
    );
  }

  Widget _card(Map<String, dynamic> report) {
    final String reportStatus = report["status"] ?? "pending";
    final snapshot = (report["snapshot"] as Map?) ?? {};
    final String title = (snapshot["title"] ?? "").toString();
    final String content = (snapshot["content"] ?? "").toString();
    final int sameCount = report["same_target_count"] ?? 1;

    return GestureDetector(
      onTap: () => _openDetail(report),
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: const Color(0xFF140028),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: const Color(0xFFEF4444).withOpacity(reportStatus == "pending" ? 0.35 : 0.1),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _tag("${report["target_type_label"] ?? "게시글"} 신고", const Color(0xFFEF4444)),
                const SizedBox(width: 8),
                _tag(report["reason_label"] ?? "기타", const Color(0xFF8B5CF6)),
                if (sameCount > 1) ...[
                  const SizedBox(width: 8),
                  _tag("누적 $sameCount건", const Color(0xFFF97316)),
                ],
                const Spacer(),
                Text(
                  reportStatusLabels[reportStatus] ?? reportStatus,
                  style: TextStyle(
                    color: reportStatusColor(reportStatus),
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            if (title.isNotEmpty)
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            if (content.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                content,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Colors.white60, height: 1.4),
              ),
            ],
            if (report["target_exists"] == false)
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: Text("※ 원본이 이미 삭제됨",
                    style: TextStyle(color: Colors.white38, fontSize: 12)),
              ),
            const SizedBox(height: 12),
            Text(
              "신고당한 회원: ${report["target_user"]?["nickname"] ?? "알 수 없음"}"
              " (경고 ${report["target_user"]?["warning_count"] ?? 0}회)",
              style: const TextStyle(color: Colors.white70, fontSize: 14),
            ),
            const SizedBox(height: 6),
            Text(
              "신고자: ${report["reporter"]?["nickname"] ?? "알 수 없음"}",
              style: const TextStyle(color: Colors.white70, fontSize: 14),
            ),
            const SizedBox(height: 10),
            const Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(
                  "상세보기",
                  style: TextStyle(
                    color: Color(0xFF8B5CF6),
                    fontWeight: FontWeight.bold,
                  ),
                ),
                SizedBox(width: 4),
                Icon(Icons.arrow_forward_ios, color: Color(0xFF8B5CF6), size: 14),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _tag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12),
      ),
    );
  }
}
