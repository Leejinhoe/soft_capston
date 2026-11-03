import 'package:flutter/material.dart';

import '../core/api_client.dart';

const _bg = Color(0xFF070018);
const _card = Color(0xFF140028);

String inboxDate(dynamic iso) {
  final d = DateTime.tryParse((iso ?? '').toString());
  if (d == null) return '';
  return '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';
}

/// 알림함 한 줄 (마이페이지 미리보기와 전체 보기 공통)
/// item: {type: warning|notice, title, body, created_at, is_unread}
class InboxTile extends StatelessWidget {
  final Map<String, dynamic> item;
  final bool compact; // 미리보기면 본문을 2줄까지만
  final VoidCallback? onTap;

  const InboxTile({super.key, required this.item, this.compact = false, this.onTap});

  @override
  Widget build(BuildContext context) {
    final bool warning = item['type'] == 'warning';
    final bool unread = item['is_unread'] == true;
    final Color color = warning ? Colors.orangeAccent : Colors.purpleAccent;
    final String body = (item['body'] ?? '').toString();

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: unread ? Colors.orange.withOpacity(0.10) : _card,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withOpacity(unread ? 0.8 : 0.35)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(warning ? Icons.warning_amber_rounded : Icons.campaign, color: color),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (unread)
                        Container(
                          margin: const EdgeInsets.only(right: 6),
                          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.redAccent,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Text('NEW',
                              style: TextStyle(
                                  color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                        ),
                      Expanded(
                        child: Text((item['title'] ?? (warning ? '받은 경고' : '공지사항')).toString(),
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                      ),
                      Text(inboxDate(item['created_at']),
                          style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ],
                  ),
                  if (body.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(body,
                        maxLines: compact ? 2 : null,
                        overflow: compact ? TextOverflow.ellipsis : null,
                        style: const TextStyle(color: Colors.white70, height: 1.5)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 마이페이지 > 알림함 전체 보기 (GET /api/users/me/inbox)
/// 열면 받은 경고를 읽음으로 표시합니다. (POST /api/users/me/inbox/read)
class InboxPage extends StatefulWidget {
  const InboxPage({super.key});

  @override
  State<InboxPage> createState() => _InboxPageState();
}

class _InboxPageState extends State<InboxPage> {
  List<Map<String, dynamic>> items = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final response = await ApiClient.get('/api/users/me/inbox');
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() => items = (data['items'] as List? ?? []).cast<Map<String, dynamic>>());
        // 화면에는 이번에 "NEW"를 그대로 보여 주고, 서버에는 읽음으로 저장합니다.
        if ((data['unread_warning_count'] ?? 0) > 0) {
          await ApiClient.post('/api/users/me/inbox/read');
        }
      }
    } catch (e) {
      debugPrint('알림함 조회 실패: $e');
    }
    if (mounted) setState(() => isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: Colors.white,
        title: Text(isLoading ? '알림함' : '알림함 (${items.length})',
            style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.purpleAccent))
          : RefreshIndicator(
              onRefresh: _load,
              child: items.isEmpty
                  ? ListView(children: const [
                      Padding(
                        padding: EdgeInsets.all(40),
                        child: Center(
                            child: Text('아직 새로운 알림이 없어요.',
                                style: TextStyle(color: Colors.white54))),
                      ),
                    ])
                  : ListView.builder(
                      padding: const EdgeInsets.all(20),
                      itemCount: items.length,
                      itemBuilder: (_, i) => InboxTile(item: items[i]),
                    ),
            ),
    );
  }
}
