import 'package:flutter/material.dart';

import '../core/api_client.dart';

const _bg = Color(0xFF070018);
const _card = Color(0xFF140028);

/// 마이페이지의 "내가 만든 동화" / "내가 올린 게시글" 공통 화면 (보기 · 수정 · 삭제)
class MyItemsPage extends StatefulWidget {
  final String title;
  final String listPath; // 예: /api/users/me/stories
  final String itemPath; // 예: /api/stories  (뒤에 /{id})
  final String emptyMessage;
  final bool showLikes;

  const MyItemsPage({
    super.key,
    required this.title,
    required this.listPath,
    required this.itemPath,
    required this.emptyMessage,
    this.showLikes = false,
  });

  const MyItemsPage.stories({super.key})
      : title = '내가 만든 동화',
        listPath = '/api/users/me/stories',
        itemPath = '/api/stories',
        emptyMessage = '아직 만든 동화가 없어요.\n첫 동화를 만들어 볼까요? 📖',
        showLikes = false;

  const MyItemsPage.posts({super.key})
      : title = '내가 올린 게시글',
        listPath = '/api/users/me/posts',
        itemPath = '/api/posts',
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
        builder: (_) => _ItemDetailPage(item: item, showLikes: widget.showLikes),
      ),
    );
    if (result == 'edit') _edit(item);
    if (result == 'delete') _delete(item);
  }

  Future<void> _edit(Map<String, dynamic> item) async {
    final updated = await Navigator.push<Map<String, dynamic>>(
      context,
      MaterialPageRoute(
        builder: (_) => _ItemEditPage(
          item: item,
          path: '${widget.itemPath}/${item['id']}',
          pageTitle: '${widget.title} 수정',
        ),
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

  Future<void> _delete(Map<String, dynamic> item) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _card,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Colors.white10),
        ),
        title: const Text('삭제할까요?',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Text(
          '"${item['title']}"을(를) 지우면 되돌릴 수 없어요.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('삭제', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (ok != true) return;

    try {
      final response = await ApiClient.delete('${widget.itemPath}/${item['id']}');
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() {
          items.removeWhere((e) => e['id'] == item['id']);
          changed = true;
        });
        _toast('삭제했어요.');
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
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
                    _metaRow(item, widget.showLikes),
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

Widget _metaRow(Map<String, dynamic> item, bool showLikes) {
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
  final bool showLikes;

  const _ItemDetailPage({required this.item, required this.showLikes});

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
          _metaRow(item, showLikes),
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

/// 제목/내용 수정 화면. 저장에 성공하면 서버가 돌려준 항목을 pop 합니다.
class _ItemEditPage extends StatefulWidget {
  final Map<String, dynamic> item;
  final String path;
  final String pageTitle;

  const _ItemEditPage(
      {required this.item, required this.path, required this.pageTitle});

  @override
  State<_ItemEditPage> createState() => _ItemEditPageState();
}

class _ItemEditPageState extends State<_ItemEditPage> {
  late final TextEditingController titleController =
      TextEditingController(text: widget.item['title'] ?? '');
  late final TextEditingController contentController =
      TextEditingController(text: widget.item['content'] ?? '');
  bool isSaving = false;

  @override
  void dispose() {
    titleController.dispose();
    contentController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final title = titleController.text.trim();
    final content = contentController.text.trim();
    if (title.isEmpty || content.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('제목과 내용을 모두 적어 주세요.')));
      return;
    }
    setState(() => isSaving = true);
    try {
      final response = await ApiClient.patch(widget.path,
          body: {'title': title, 'content': content});
      if (!mounted) return;
      if (response.statusCode == 200) {
        Navigator.pop(context, Map<String, dynamic>.from(ApiClient.decode(response)));
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ApiClient.errorMessage(response))));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('서버에 연결하지 못했어요.')));
      }
    }
    if (mounted) setState(() => isSaving = false);
  }

  InputDecoration _decoration(String label) => InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white70),
        filled: true,
        fillColor: _card,
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: Colors.white10),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: Colors.purpleAccent),
        ),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: Colors.white,
        title: Text(widget.pageTitle),
        actions: [
          TextButton(
            onPressed: isSaving ? null : _save,
            child: isSaving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.purpleAccent))
                : const Text('저장',
                    style: TextStyle(
                        color: Colors.purpleAccent,
                        fontSize: 16,
                        fontWeight: FontWeight.bold)),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          TextField(
            controller: titleController,
            maxLength: 50,
            style: const TextStyle(color: Colors.white),
            decoration: _decoration('제목'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: contentController,
            minLines: 12,
            maxLines: null,
            style: const TextStyle(color: Colors.white, height: 1.6),
            decoration: _decoration('내용'),
          ),
        ],
      ),
    );
  }
}
