import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/linked_items.dart';

const _bg = Color(0xFF070018);
const _card = Color(0xFF140028);

/// 마이페이지의 "내가 만든 동화" / "내가 올린 게시글" 공통 화면 (보기 · 수정 · 삭제)
class MyItemsPage extends StatefulWidget {
  final String title;
  final String listPath; // 예: /api/users/me/stories
  final LinkedKind kind; // 동화 / 게시글 (수정·삭제 API와 "함께 할까요?" 팝업 문구)
  final String emptyMessage;
  final bool showLikes;

  const MyItemsPage({
    super.key,
    required this.title,
    required this.listPath,
    required this.kind,
    required this.emptyMessage,
    this.showLikes = false,
  });

  const MyItemsPage.stories({super.key})
      : title = '내가 만든 동화',
        listPath = '/api/users/me/stories',
        kind = LinkedKind.story,
        emptyMessage = '아직 만든 동화가 없어요.\n첫 동화를 만들어 볼까요? 📖',
        showLikes = false;

  const MyItemsPage.posts({super.key})
      : title = '내가 올린 게시글',
        listPath = '/api/users/me/posts',
        kind = LinkedKind.post,
        emptyMessage = '아직 커뮤니티에 올린 글이 없어요.',
        showLikes = true;

  @override
  State<MyItemsPage> createState() => _MyItemsPageState();
}

class _MyItemsPageState extends State<MyItemsPage> {
  List<Map<String, dynamic>> items = [];
  bool isLoading = true;
  String? error;
  bool changed = false; // 수정/삭제가 있었으면 마이페이지 숫자를 새로 불러오도록 알림

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      isLoading = true;
      error = null;
    });
    try {
      final response = await ApiClient.get(widget.listPath);
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          items = (data as List).cast<Map<String, dynamic>>();
          isLoading = false;
        });
      } else {
        setState(() {
          error = ApiClient.errorMessage(response);
          isLoading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        error = '서버에 연결하지 못했어요.';
        isLoading = false;
      });
    }
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _openDetail(Map<String, dynamic> item) async {
    final result = await Navigator.push<String>(
      context,
      MaterialPageRoute(
        builder: (_) => _ItemDetailPage(
            item: item, kind: widget.kind, showLikes: widget.showLikes),
      ),
    );
    if (result == 'edit') _edit(item);
    if (result == 'delete') _delete(item);
  }

  Future<void> _edit(Map<String, dynamic> item) async {
    final updated = await Navigator.push<Map<String, dynamic>>(
      context,
      MaterialPageRoute(
        builder: (_) => LinkedItemEditPage(kind: widget.kind, item: item),
      ),
    );
    if (updated == null || !mounted) return;
    setState(() {
      final i = items.indexWhere((e) => e['id'] == updated['id']);
      if (i >= 0) items[i] = updated;
      changed = true;
    });
    _toast('수정했어요.');
  }

  /// 연결된 동화/게시글이 있으면 "함께 지울까요?"를 물어봅니다.
  Future<void> _delete(Map<String, dynamic> item) async {
    final deleted = await deleteLinkedItem(context, widget.kind, item);
    if (!deleted || !mounted) return;
    setState(() {
      items.removeWhere((e) => e['id'] == item['id']);
      changed = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, changed);
      },
      child: Scaffold(
        backgroundColor: _bg,
        appBar: AppBar(
          backgroundColor: _bg,
          foregroundColor: Colors.white,
          title: Text(widget.title),
        ),
        body: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (isLoading) {
      return const Center(
          child: CircularProgressIndicator(color: Colors.purpleAccent));
    }
    if (error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(error!, style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 12),
            TextButton(
              onPressed: _load,
              child: const Text('다시 불러오기',
                  style: TextStyle(color: Colors.purpleAccent)),
            ),
          ],
        ),
      );
    }
    if (items.isEmpty) {
      return Center(
        child: Text(
          widget.emptyMessage,
          textAlign: TextAlign.center,
          style: const TextStyle(color: Colors.white54, fontSize: 16, height: 1.6),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      color: Colors.purpleAccent,
      child: ListView.builder(
        padding: const EdgeInsets.all(20),
        itemCount: items.length,
        itemBuilder: (context, index) => _itemCard(items[index]),
      ),
    );
  }

  Widget _itemCard(Map<String, dynamic> item) {
    final content = (item['content'] ?? '').toString().replaceAll('\n', ' ');
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () => _openDetail(item),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 14, 6, 14),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item['title'] ?? '',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 17,
                          fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      content,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white60, height: 1.4),
                    ),
                    const SizedBox(height: 8),
                    _metaRow(item, widget.kind, widget.showLikes),
                  ],
                ),
              ),
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert, color: Colors.white54),
                color: _card,
                onSelected: (value) {
                  if (value == 'edit') _edit(item);
                  if (value == 'delete') _delete(item);
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(
                      value: 'edit',
                      child: Text('수정', style: TextStyle(color: Colors.white))),
                  PopupMenuItem(
                      value: 'delete',
                      child: Text('삭제', style: TextStyle(color: Colors.redAccent))),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

String _date(dynamic iso) {
  final d = DateTime.tryParse((iso ?? '').toString());
  if (d == null) return '';
  return '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';
}

Widget _metaRow(Map<String, dynamic> item, LinkedKind kind, bool showLikes) {
  final genre = (item['genre'] ?? '').toString();
  return Wrap(
    spacing: 10,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      if (genre.isNotEmpty)
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.purple.withOpacity(0.2),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(genre,
              style: const TextStyle(color: Colors.purpleAccent, fontSize: 12)),
        ),
      Text(_date(item['created_at']),
          style: const TextStyle(color: Colors.white38, fontSize: 12)),
      if (hasLink(item))
        Text(kind.linkedLabel,
            style: const TextStyle(color: Colors.purpleAccent, fontSize: 12)),
      if (showLikes)
        Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.favorite, color: Colors.pinkAccent, size: 14),
          const SizedBox(width: 4),
          Text('${item['likes_count'] ?? 0}',
              style: const TextStyle(color: Colors.white70, fontSize: 12)),
        ]),
    ],
  );
}

/// 전체 내용 보기. 하단 버튼으로 수정/삭제를 고르면 목록 화면이 처리합니다.
class _ItemDetailPage extends StatelessWidget {
  final Map<String, dynamic> item;
  final LinkedKind kind;
  final bool showLikes;

  const _ItemDetailPage(
      {required this.item, required this.kind, required this.showLikes});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: Colors.white,
        title: Text(item['title'] ?? '', overflow: TextOverflow.ellipsis),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          _metaRow(item, kind, showLikes),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _card,
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white10),
            ),
            child: SelectableText(
              item['content'] ?? '',
              style: const TextStyle(color: Colors.white, fontSize: 17, height: 1.8),
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.redAccent,
                    side: const BorderSide(color: Colors.redAccent),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: () => Navigator.pop(context, 'delete'),
                  icon: const Icon(Icons.delete_outline),
                  label: const Text('삭제'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purpleAccent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: () => Navigator.pop(context, 'edit'),
                  icon: const Icon(Icons.edit),
                  label: const Text('수정'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
