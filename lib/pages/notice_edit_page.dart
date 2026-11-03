import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';

/// 관리자 > 공지 등록 / 수정
/// 대상: 전체 회원 또는 특정 회원(아이디로 여러 명). 저장하면 true를 돌려줍니다.
class NoticeEditPage extends StatefulWidget {
  final Map<String, dynamic>? notice; // null이면 새 공지

  const NoticeEditPage({super.key, this.notice});

  @override
  State<NoticeEditPage> createState() => _NoticeEditPageState();
}

class _NoticeEditPageState extends State<NoticeEditPage> {
  late final titleController = TextEditingController(text: widget.notice?['title'] ?? '');
  late final contentController = TextEditingController(text: widget.notice?['content'] ?? '');
  final idController = TextEditingController();

  late String target = widget.notice?['target'] == 'users' ? 'users' : 'all';
  // 선택한 회원: {id, nickname}
  late List<Map<String, dynamic>> selected = [
    for (final t in (widget.notice?['target_users'] as List? ?? []))
      Map<String, dynamic>.from(t as Map),
  ];
  bool checking = false;
  bool saving = false;

  bool get isEdit => widget.notice != null;

  @override
  void dispose() {
    titleController.dispose();
    contentController.dispose();
    idController.dispose();
    super.dispose();
  }

  // 아이디가 실제로 있는지 확인하고 받는 사람에 추가합니다.
  Future<void> addUser() async {
    final id = idController.text.trim();
    if (id.isEmpty) return;
    if (selected.any((u) => u['id'] == id)) {
      adminToast(context, '이미 추가한 아이디예요.');
      return;
    }
    setState(() => checking = true);
    try {
      final response = await ApiClient.get('/api/admin/users/${Uri.encodeComponent(id)}');
      if (!mounted) return;
      if (response.statusCode == 200) {
        final user = ApiClient.decode(response);
        setState(() {
          selected.add({'id': user['id'], 'nickname': user['nickname'], 'exists': true});
          idController.clear();
        });
      } else {
        adminToast(context, "'$id' 아이디의 회원이 없어요.");
      }
    } catch (e) {
      if (mounted) adminToast(context, '통신 오류가 발생했어요: $e');
    }
    if (mounted) setState(() => checking = false);
  }

  Future<void> save() async {
    final title = titleController.text.trim();
    final content = contentController.text.trim();
    if (title.isEmpty || content.isEmpty) {
      adminToast(context, '제목과 내용을 입력해 주세요.');
      return;
    }
    // 그새 탈퇴한 회원은 받는 사람에서 뺍니다.
    final ids = [for (final u in selected) if (u['exists'] != false) u['id']];
    if (target == 'users' && ids.isEmpty) {
      adminToast(context, '공지를 받을 회원을 한 명 이상 추가해 주세요.');
      return;
    }
    setState(() => saving = true);
    try {
      final body = {
        'title': title,
        'content': content,
        'target': target,
        'user_ids': target == 'users' ? ids : [],
      };
      final response = isEdit
          ? await ApiClient.patch('/api/admin/notices/${widget.notice!['id']}', body: body)
          : await ApiClient.post('/api/admin/notices', body: body);
      if (!mounted) return;
      if (adminOk(context, response)) {
        adminToast(context, isEdit ? '공지를 수정했어요.' : '공지를 등록했어요.');
        Navigator.pop(context, true);
        return;
      }
    } catch (e) {
      if (mounted) adminToast(context, '통신 오류가 발생했어요: $e');
    }
    if (mounted) setState(() => saving = false);
  }

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 8, top: 18),
        child: Text(text,
            style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold)),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.bg,
      appBar: adminAppBar(isEdit ? '공지 수정' : '공지 등록'),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _label('받는 사람'),
            Row(
              children: [
                adminChip(
                    label: '전체 회원',
                    selected: target == 'all',
                    onTap: () => setState(() => target = 'all')),
                adminChip(
                    label: '특정 회원',
                    selected: target == 'users',
                    onTap: () => setState(() => target = 'users')),
              ],
            ),
            if (target == 'users') ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: idController,
                      style: const TextStyle(color: Colors.white),
                      onSubmitted: (_) => addUser(),
                      decoration: adminInputDecoration('회원 아이디 입력 후 추가'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    height: 52,
                    child: ElevatedButton(
                      onPressed: checking ? null : addUser,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AdminColors.purple,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: checking
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('추가'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              if (selected.isEmpty)
                const Text('아직 추가한 회원이 없어요.', style: TextStyle(color: Colors.white38))
              else
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final u in selected)
                      InputChip(
                        label: Text(
                          u['exists'] == false
                              ? '${u['id']} (탈퇴)'
                              : '${u['nickname']} (@${u['id']})',
                        ),
                        labelStyle: TextStyle(
                            color: u['exists'] == false ? Colors.white38 : Colors.white),
                        backgroundColor: AdminColors.card,
                        side: BorderSide(color: AdminColors.purple.withOpacity(0.5)),
                        deleteIconColor: Colors.white54,
                        onDeleted: () => setState(() => selected.remove(u)),
                      ),
                  ],
                ),
            ],
            _label('제목'),
            TextField(
              controller: titleController,
              maxLength: 100,
              style: const TextStyle(color: Colors.white),
              decoration: adminInputDecoration('공지 제목'),
            ),
            _label('내용'),
            TextField(
              controller: contentController,
              maxLength: 5000,
              minLines: 8,
              maxLines: 16,
              style: const TextStyle(color: Colors.white, height: 1.5),
              decoration: adminInputDecoration('아이들이 읽기 쉬운 다정한 말투로 적어 주세요.'),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton.icon(
                onPressed: saving ? null : save,
                icon: const Icon(Icons.campaign),
                label: Text(isEdit ? '수정하기' : '등록하기',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AdminColors.green,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
