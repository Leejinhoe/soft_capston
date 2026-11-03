import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';
import 'notice_edit_page.dart';

/// 관리자 > 공지사항 목록 (GET /api/admin/notices), 등록 / 수정 / 삭제
class NoticeAdminPage extends StatefulWidget {
  const NoticeAdminPage({super.key});

  @override
  State<NoticeAdminPage> createState() => _NoticeAdminPageState();
}

class _NoticeAdminPageState extends State<NoticeAdminPage> {
  List<Map<String, dynamic>> notices = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final response = await ApiClient.get('/api/admin/notices');
      if (!mounted) return;
      if (adminOk(context, response)) {
        setState(() => notices =
            (ApiClient.decode(response) as List).cast<Map<String, dynamic>>());
      }
    } catch (e) {
      if (mounted) adminToast(context, '공지사항을 불러오지 못했어요: $e');
    }
    if (mounted) setState(() => isLoading = false);
  }

  Future<void> _edit([Map<String, dynamic>? notice]) async {
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => NoticeEditPage(notice: notice)),
    );
    if (saved == true) load();
  }

  Future<void> _delete(Map<String, dynamic> notice) async {
    final ok = await adminConfirm(
      context,
      title: '공지 삭제',
      message: "'${notice['title']}' 공지를 삭제할까요?\n회원 알림함에서도 사라져요.",
      okText: '삭제',
      okColor: AdminColors.red,
    );
    if (!ok) return;
    try {
      final response = await ApiClient.delete('/api/admin/notices/${notice['id']}');
      if (!mounted || !adminOk(context, response)) return;
      adminToast(context, '공지사항을 삭제했어요.');
      load();
    } catch (e) {
      if (mounted) adminToast(context, '통신 오류가 발생했어요: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.bg,
      appBar: adminAppBar('공지사항'),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(),
        backgroundColor: AdminColors.green,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('공지 등록', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: isLoading
          ? adminLoading
          : notices.isEmpty
              ? adminEmpty('등록된 공지사항이 없어요.')
              : RefreshIndicator(
                  onRefresh: load,
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                    itemCount: notices.length,
                    itemBuilder: (context, index) => _card(notices[index]),
                  ),
                ),
    );
  }

  Widget _card(Map<String, dynamic> n) {
    final bool forUsers = n['target'] == 'users';
    final targets = (n['target_users'] as List? ?? []).cast<Map<String, dynamic>>();
    final String targetText = !forUsers
        ? '전체 회원'
        : targets.length <= 3
            ? targets.map((t) => t['id']).join(', ')
            : '${targets.take(3).map((t) => t['id']).join(', ')} 외 ${targets.length - 3}명';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.fromLTRB(18, 14, 8, 14),
      decoration: BoxDecoration(
        color: AdminColors.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AdminColors.green.withOpacity(0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: InkWell(
              onTap: () => _edit(n),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      adminTag(forUsers ? '특정 회원' : '전체',
                          forUsers ? AdminColors.orange : AdminColors.green),
                      Text(adminDate(n['created_at']),
                          style: const TextStyle(color: Colors.white38, fontSize: 12)),
                      if ((n['updated_at'] ?? '').toString().isNotEmpty)
                        const Text('(수정됨)',
                            style: TextStyle(color: Colors.white38, fontSize: 12)),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text(n['title'] ?? '',
                      style: const TextStyle(
                          color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 6),
                  Text(n['content'] ?? '',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white60, height: 1.4)),
                  const SizedBox(height: 8),
                  Text('대상: $targetText',
                      style: const TextStyle(color: Colors.white54, fontSize: 13)),
                ],
              ),
            ),
          ),
          Column(
            children: [
              IconButton(
                tooltip: '수정',
                icon: const Icon(Icons.edit, color: Colors.white70),
                onPressed: () => _edit(n),
              ),
              IconButton(
                tooltip: '삭제',
                icon: const Icon(Icons.delete_outline, color: AdminColors.red),
                onPressed: () => _delete(n),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
