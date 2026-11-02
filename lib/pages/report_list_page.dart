import 'package:flutter/material.dart';
import '../core/api_client.dart';
import 'report_detail_page.dart';

class ReportListPage extends StatefulWidget {
  const ReportListPage({super.key});

  @override
  State<ReportListPage> createState() => _ReportListPageState();
}

class _ReportListPageState extends State<ReportListPage> {
  Future<void> giveWarning(String authorName) async {
    if (authorName.isEmpty) {
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

  List<dynamic> reports = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchReports();
  }

  Future<void> fetchReports() async {
    try {
      final response = await ApiClient.get("/admin/reports");

      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() {
          reports = ApiClient.decode(response) ?? [];
          isLoading = false;
        });
      } else {
        setState(() {
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        isLoading = false;
      });

      debugPrint("신고 목록 불러오기 오류: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),

      appBar: AppBar(
        backgroundColor: const Color(0xFF140028),
        foregroundColor: Colors.white,
        title: const Text(
          "신고 관리",
          style: TextStyle(
            fontWeight: FontWeight.bold,
          ),
        ),
      ),

      body: isLoading
          ? const Center(
        child: CircularProgressIndicator(
          color: Color(0xFF8B5CF6),
        ),
      )
          : reports.isEmpty
          ? const Center(
        child: Text(
          "접수된 신고가 없습니다.",
          style: TextStyle(
            color: Colors.white70,
            fontSize: 16,
          ),
        ),
      )
          : ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: reports.length,
        itemBuilder: (context, index) {
          final report = reports[index];

          return GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => ReportDetailPage(
                    report: Map<String, dynamic>.from(report),
                  ),
                ),
              );
            },

            child: Container(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.all(18),

              decoration: BoxDecoration(
                color: const Color(0xFF140028),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: const Color(0xFFEF4444)
                      .withOpacity(0.35),
                ),
              ),

              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [

                  Row(
                    children: [

                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),

                        decoration: BoxDecoration(
                          color: const Color(0xFFEF4444)
                              .withOpacity(0.15),
                          borderRadius:
                          BorderRadius.circular(10),
                        ),

                        child: const Text(
                          "신고 접수",
                          style: TextStyle(
                            color: Color(0xFFEF4444),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),

                      const Spacer(),

                      Text(
                        report["status"] == "waiting"
                            ? "처리 대기"
                            : "처리 완료",

                        style: TextStyle(
                          color: report["status"] == "waiting"
                              ? const Color(0xFFF97316)
                              : Colors.greenAccent,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 16),

                  Text(
                    report["story_title"] ?? "제목 없음",
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 19,
                      fontWeight: FontWeight.bold,
                    ),
                  ),

                  const SizedBox(height: 12),

                  Text(
                    "작성자: ${report["author"] ?? "알 수 없음"}",
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),

                  const SizedBox(height: 6),

                  Text(
                    "신고자: ${report["reporter"] ?? "알 수 없음"}",
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),

                  const SizedBox(height: 6),

                  Text(
                    "신고 사유: ${report["reason"] ?? "사유 없음"}",
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),

                  const SizedBox(height: 12),

                  Text(
                    "신고 ID: ${report["id"]}",
                    style: const TextStyle(
                      color: Colors.white38,
                      fontSize: 12,
                    ),
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
                      Icon(
                        Icons.arrow_forward_ios,
                        color: Color(0xFF8B5CF6),
                        size: 14,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}