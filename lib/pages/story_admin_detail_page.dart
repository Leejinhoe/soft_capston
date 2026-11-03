import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';

/// 관리자 > 동화 상세 (GET /api/admin/stories/{id}), 관리자 삭제
/// 삭제하면 목록에 true를 돌려줍니다.
class StoryAdminDetailPage extends StatefulWidget {
  final String storyId;

  const StoryAdminDetailPage({super.key, required this.storyId});

  @override
  State<StoryAdminDetailPage> createState() => _StoryAdminDetailPageState();
}

class _StoryAdminDetailPageState extends State<StoryAdminDetailPage> {
  Map<String, dynamic>? story;
  bool isLoading = true;
  bool busy = false;

  String get _path => '/api/admin/stories/${widget.storyId}';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final response = await ApiClient.get(_path);
      if (!mounted) return;
      if (adminOk(context, response)) {
        setState(() => story = Map<String, dynamic>.from(ApiClient.decode(response)));
      }
    } catch (e) {
      if (mounted) adminToast(context, '동화를 불러오지 못했어요: $e');
    }
    if (mounted) setState(() => isLoading = false);
  }

  Future<void> deleteStory() async {
    final s = story;
    if (s == null) return;
    final ok = await adminConfirm(
      context,
      title: '동화 삭제',
      message: "'${s['title']}' 동화를 삭제할까요?\n되돌릴 수 없어요.",
      okText: '삭제',
      okColor: AdminColors.red,
    );
    if (!ok || !mounted) return;

    // 커뮤니티에 공유된 동화면 연결된 게시글도 지울지 묻습니다.
    bool withLinked = false;
    if (s['shared'] == true) {
      final answer = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AdminColors.card,
          title: const Text('연결된 게시글',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          content: const Text('이 동화는 커뮤니티에 공유돼 있어요.\n연결된 게시글도 같이 지울까요?',
              style: TextStyle(color: Colors.white70, height: 1.5)),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('동화만 삭제', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: ElevatedButton.styleFrom(
                  backgroundColor: AdminColors.red, foregroundColor: Colors.white),
              child: const Text('게시글도 삭제'),
            ),
          ],
        ),
      );
      if (answer == null) return; // 바깥을 눌러 닫으면 취소
      withLinked = answer;
    }

    setState(() => busy = true);
    try {
      final response = await ApiClient.delete('$_path?with_linked=$withLinked');
      if (!mounted) return;
      if (adminOk(context, response)) {
        adminToast(context, ApiClient.decode(response)['message'] ?? '삭제했어요.');
        Navigator.pop(context, true);
        return;
      }
    } catch (e) {
      if (mounted) adminToast(context, '통신 오류가 발생했어요: $e');
    }
    if (mounted) setState(() => busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.bg,
      appBar: adminAppBar('동화 상세', actions: [
        if (story != null)
          IconButton(
            tooltip: '삭제',
            icon: const Icon(Icons.delete_outline),
            onPressed: busy ? null : deleteStory,
          ),
      ]),
      body: isLoading
          ? adminLoading
          : story == null
              ? adminEmpty('동화를 찾지 못했어요.')
              : _body(story!),
    );
  }

  Widget _body(Map<String, dynamic> s) {
    final author = (s['author'] as Map?) ?? {};
    final String genre = (s['genre'] ?? '').toString();
    final bool shared = s['shared'] == true;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s['title'] ?? '',
              style: const TextStyle(
                  color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Wrap(spacing: 6, runSpacing: 6, children: [
            if (genre.isNotEmpty) adminTag(genre, AdminColors.purple),
            adminTag(shared ? '🌐 커뮤니티에 공유됨' : '비공개',
                shared ? AdminColors.green : Colors.white38),
          ]),
          const SizedBox(height: 12),
          Text(
            author['exists'] == false
                ? '작성자: 탈퇴한 회원 (@${author['id']})'
                : '작성자: ${author['nickname']} (@${author['id']})',
            style: const TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 4),
          Text(
            '생성일: ${adminDate(s['created_at'])}'
            '${(s['updated_at'] ?? '').toString().isEmpty ? '' : '  ·  수정: ${adminDate(s['updated_at'])}'}',
            style: const TextStyle(color: Colors.white38, fontSize: 13),
          ),
          const SizedBox(height: 20),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AdminColors.card,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AdminColors.blue.withOpacity(0.25)),
            ),
            child: SelectableText(
              (s['content'] ?? '').toString(),
              style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.8),
            ),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: ElevatedButton.icon(
              onPressed: busy ? null : deleteStory,
              icon: const Icon(Icons.delete),
              label: const Text('관리자 삭제', style: TextStyle(fontWeight: FontWeight.bold)),
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.red,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
