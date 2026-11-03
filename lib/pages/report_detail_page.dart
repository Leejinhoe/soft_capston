import 'package:flutter/material.dart';
import '../core/api_client.dart';
import 'report_list_page.dart';

/// 관리자 > 신고 상세 (경고 주기, 처리 완료 / 반려)
/// 상태를 바꿨거나 경고를 줬으면 목록에 true를 돌려줍니다.
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
  late Map<String, dynamic> report = Map<String, dynamic>.from(widget.report);
  bool changed = false;
  bool busy = false;

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  // 신고당한 회원에게 경고 (공개 id로 정확히 찾음)
  Future<void> giveWarning() async {
    final target = (report["target_user"] as Map?) ?? {};
    final String userId = (target["id"] ?? "").toString();
    final String nickname = (target["nickname"] ?? "").toString();
    if (userId.isEmpty) {
      _toast("회원 정보가 없어 경고를 부여할 수 없습니다.");
      return;
    }

    setState(() => busy = true);
    try {
      final response = await ApiClient.put(
        "/admin/warning/${Uri.encodeComponent(userId)}",
        body: {"reason": "신고 처리: ${report["reason_label"] ?? ""}"},
      );
      if (!mounted) return;
      if (response.statusCode == 200) {
        final count = ApiClient.decode(response)["warning_count"];
        setState(() {
          changed = true;
          report["target_user"] = {...target, "warning_count": count};
        });
        _toast("'$nickname'님에게 경고 1회를 부여했습니다. (누적 $count회)");
      } else {
        _toast("회원 정보를 찾을 수 없거나 경고 처리에 실패했습니다.");
      }
    } catch (e) {
      if (mounted) _toast("통신 오류가 발생했습니다: $e");
    }
    if (mounted) setState(() => busy = false);
  }

  Future<void> updateStatus(String status) async {
    setState(() => busy = true);
    try {
      final response = await ApiClient.patch(
        "/api/admin/reports/${report["id"]}",
        body: {"status": status},
      );
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() {
          changed = true;
          report = Map<String, dynamic>.from(ApiClient.decode(response));
        });
        _toast("'${reportStatusLabels[status]}'(으)로 바꿨습니다.");
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (e) {
      if (mounted) _toast("통신 오류가 발생했습니다: $e");
    }
    if (mounted) setState(() => busy = false);
  }

  String _date(dynamic iso) {
    final d = DateTime.tryParse((iso ?? '').toString());
    if (d == null) return '';
    final local = d.isUtc ? d.toLocal() : DateTime.utc(d.year, d.month, d.day, d.hour, d.minute).toLocal();
    return '${local.year}.${local.month.toString().padLeft(2, '0')}.${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final String status = report["status"] ?? "pending";
    final snapshot = (report["snapshot"] as Map?) ?? {};
    final target = (report["target_user"] as Map?) ?? {};
    final reporter = (report["reporter"] as Map?) ?? {};
    final String detail = (report["detail"] ?? "").toString();
    final String memo = (report["admin_memo"] ?? "").toString();

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, changed);
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF070018),
        appBar: AppBar(
          backgroundColor: const Color(0xFF140028),
          foregroundColor: Colors.white,
          title: const Text("신고 상세", style: TextStyle(fontWeight: FontWeight.bold)),
        ),
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.report, color: Color(0xFFEF4444)),
                  const SizedBox(width: 8),
                  Text(
                    "${report["target_type_label"] ?? "게시글"} 신고",
                    style: const TextStyle(
                        color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  Text(
                    reportStatusLabels[status] ?? status,
                    style: TextStyle(
                        color: reportStatusColor(status), fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              _buildInfoCard(
                title: report["target_exists"] == false
                    ? "신고된 내용 (원본 삭제됨, 신고 당시 내용)"
                    : "신고된 내용 (신고 당시)",
                icon: Icons.description,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if ((snapshot["title"] ?? "").toString().isNotEmpty)
                      Text(
                        snapshot["title"],
                        style: const TextStyle(
                            color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                    if ((snapshot["content"] ?? "").toString().isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(snapshot["content"],
                          style: const TextStyle(color: Colors.white70, height: 1.5)),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 14),

              _buildInfoCard(
                title: "신고 사유",
                icon: Icons.warning_amber,
                child: Text(
                  detail.isEmpty
                      ? (report["reason_label"] ?? "기타")
                      : "${report["reason_label"] ?? "기타"}\n$detail",
                  style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.5),
                ),
              ),
              const SizedBox(height: 14),

              _buildInfoCard(
                title: "신고당한 회원",
                icon: Icons.person,
                child: Text(
                  "${target["nickname"] ?? "알 수 없음"} (${target["id"] ?? ""})\n"
                  "누적 경고 ${target["warning_count"] ?? 0}회 · "
                  "${target["status"] == "banned" ? "정지됨" : "활동 중"}",
                  style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.5),
                ),
              ),
              const SizedBox(height: 14),

              _buildInfoCard(
                title: "신고자",
                icon: Icons.person_outline,
                child: Text(
                  "${reporter["nickname"] ?? "알 수 없음"} (${reporter["id"] ?? ""})",
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                ),
              ),
              const SizedBox(height: 14),

              _buildInfoCard(
                title: "접수 / 처리",
                icon: Icons.calendar_today,
                child: Text(
                  "접수: ${_date(report["created_at"])}"
                  "${(report["handled_at"] ?? "").toString().isEmpty ? "" : "\n처리: ${_date(report["handled_at"])} (${report["handled_by"]})"}"
                  "${memo.isEmpty ? "" : "\n메모: $memo"}"
                  "\n같은 대상 신고: ${report["same_target_count"] ?? 1}건",
                  style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.6),
                ),
              ),
              const SizedBox(height: 14),

              _buildInfoCard(
                title: "신고 ID / 대상 ID",
                icon: Icons.tag,
                child: Text(
                  "${report["id"] ?? ""}\n${report["target_type"]}: ${report["target_id"] ?? ""}"
                  "${(report["post_id"] ?? "").toString().isEmpty ? "" : "\n게시글: ${report["post_id"]}"}",
                  style: const TextStyle(color: Colors.white38, fontSize: 13, height: 1.5),
                ),
              ),

              const SizedBox(height: 30),

              SizedBox(
                width: double.infinity,
                height: 55,
                child: ElevatedButton.icon(
                  onPressed: busy ? null : giveWarning,
                  icon: const Icon(Icons.warning_amber),
                  label: const Text(
                    "신고당한 회원에게 경고",
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFF97316),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              Row(
                children: [
                  Expanded(
                    child: SizedBox(
                      height: 55,
                      child: OutlinedButton.icon(
                        onPressed: busy || status == "resolved"
                            ? null
                            : () => updateStatus("resolved"),
                        icon: const Icon(Icons.check),
                        label: const Text("처리 완료",
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.greenAccent,
                          side: const BorderSide(color: Colors.greenAccent),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16)),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: SizedBox(
                      height: 55,
                      child: OutlinedButton.icon(
                        onPressed: busy || status == "rejected"
                            ? null
                            : () => updateStatus("rejected"),
                        icon: const Icon(Icons.block),
                        label: const Text("반려",
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white70,
                          side: const BorderSide(color: Colors.white38),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16)),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              if (status != "pending") ...[
                const SizedBox(height: 8),
                Center(
                  child: TextButton(
                    onPressed: busy ? null : () => updateStatus("pending"),
                    child: const Text("처리 대기로 되돌리기",
                        style: TextStyle(color: Colors.white54)),
                  ),
                ),
              ],
            ],
          ),
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
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: const Color(0xFF8B5CF6), size: 20),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
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
