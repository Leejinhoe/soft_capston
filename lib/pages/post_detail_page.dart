import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/linked_items.dart';
import '../widgets/mini_profile_sheet.dart';
import '../widgets/post_card.dart';
import '../widgets/report_sheet.dart';

/// 상세 화면에서 돌아갈 때 목록에 알려줄 변화
class PostDetailResult {
  final bool deleted;
  final Map<String, dynamic>? summary; // 바뀐 제목/좋아요 수/댓글 수 등

  const PostDetailResult({this.deleted = false, this.summary});
}

/// 커뮤니티 게시글 상세: 동화 본문, 작성자, 작성일, 좋아요·스크랩·댓글
class PostDetailPage extends StatefulWidget {
  final String postId;

  const PostDetailPage({super.key, required this.postId});

  @override
  State<PostDetailPage> createState() => _PostDetailPageState();
}

class _PostDetailPageState extends State<PostDetailPage> {
  final TextEditingController _commentController = TextEditingController();

  Map<String, dynamic>? _post;
  List<Map<String, dynamic>> _comments = [];
  bool _isLoading = true;
  String? _error;
  bool _likeBusy = false;
  bool _scrapBusy = false;
  bool _sendingComment = false;

  String get _base => '/api/community/posts/${widget.postId}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final responses = await Future.wait([
        ApiClient.get(_base),
        ApiClient.get('$_base/comments'),
      ]);
      if (!mounted) return;
      final postRes = responses[0];
      if (postRes.statusCode != 200) {
        setState(() {
          _error = ApiClient.errorMessage(postRes);
          _isLoading = false;
        });
        return;
      }
      final commentRes = responses[1];
      setState(() {
        _post = Map<String, dynamic>.from(ApiClient.decode(postRes));
        _comments = commentRes.statusCode == 200
            ? (ApiClient.decode(commentRes) as List).cast<Map<String, dynamic>>()
            : [];
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = '서버에 연결하지 못했어요.';
        _isLoading = false;
      });
    }
  }

  void _close() {
    final post = _post;
    Navigator.pop(
      context,
      post == null
          ? null
          : PostDetailResult(summary: {
              'title': post['title'],
              'likes_count': post['likes_count'],
              'comments_count': post['comments_count'],
            }),
    );
  }

  // ---------- 좋아요 / 스크랩 ----------
  Future<void> _toggleLike() async {
    if (_likeBusy || _post == null) return;
    setState(() => _likeBusy = true);
    try {
      final response = await ApiClient.post('$_base/like');
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          _post!['liked'] = data['liked'];
          _post!['likes_count'] = data['likes_count'];
        });
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
    if (mounted) setState(() => _likeBusy = false);
  }

  Future<void> _toggleScrap() async {
    if (_scrapBusy || _post == null) return;
    setState(() => _scrapBusy = true);
    try {
      final response = await ApiClient.post('$_base/scrap');
      if (!mounted) return;
      if (response.statusCode == 200) {
        final scrapped = ApiClient.decode(response)['scrapped'] == true;
        setState(() => _post!['scrapped'] = scrapped);
        _toast(scrapped ? '스크랩했어요! 마이페이지에서 다시 볼 수 있어요 📌' : '스크랩을 취소했어요.');
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
    if (mounted) setState(() => _scrapBusy = false);
  }

  // ---------- 댓글 ----------
  Future<void> _sendComment() async {
    final content = _commentController.text.trim();
    if (content.isEmpty || _sendingComment) return;
    setState(() => _sendingComment = true);
    try {
      final response = await ApiClient.post('$_base/comments', body: {'content': content});
      if (!mounted) return;
      if (response.statusCode == 200) {
        _commentController.clear();
        FocusScope.of(context).unfocus();
        setState(() {
          _comments.add(Map<String, dynamic>.from(ApiClient.decode(response)));
          _post!['comments_count'] = (_post!['comments_count'] ?? 0) + 1;
        });
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
    if (mounted) setState(() => _sendingComment = false);
  }

  Future<void> _deleteComment(Map<String, dynamic> comment) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: kCommunityCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Colors.white10),
        ),
        title: const Text('댓글을 지울까요?',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
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
      final response = await ApiClient.delete('/api/community/comments/${comment['id']}');
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() {
          _comments.removeWhere((c) => c['id'] == comment['id']);
          final count = (_post!['comments_count'] ?? 1) - 1;
          _post!['comments_count'] = count < 0 ? 0 : count;
        });
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
  }

  // ---------- 내 글 수정 / 삭제 (연결된 동화에도 반영/삭제할지 물어봄) ----------
  Future<void> _edit() async {
    final updated = await Navigator.push<Map<String, dynamic>>(
      context,
      MaterialPageRoute(
        builder: (_) => LinkedItemEditPage(kind: LinkedKind.post, item: _post!),
      ),
    );
    if (updated == null || !mounted) return;
    setState(() {
      _post!['title'] = updated['title'];
      _post!['content'] = updated['content'];
      _post!['linked_id'] = updated['linked_id'] ?? '';
    });
    _toast('수정했어요.');
  }

  Future<void> _delete() async {
    final deleted = await deleteLinkedItem(context, LinkedKind.post, _post!);
    if (deleted && mounted) {
      Navigator.pop(context, const PostDetailResult(deleted: true));
    }
  }

  // ---------- 신고 / 작성자 프로필 ----------
  Future<void> _report() async {
    final reported = await showReportSheet(context,
        target: ReportTarget.post, targetId: widget.postId);
    if (reported && mounted) setState(() => _post!['reported'] = true);
  }

  Future<void> _reportComment(Map<String, dynamic> comment) async {
    final reported = await showReportSheet(context,
        target: ReportTarget.comment, targetId: comment['id']);
    if (reported && mounted) setState(() => comment['reported'] = true);
  }

  void _openProfile(Map<String, dynamic>? author) {
    final id = (author?['id'] ?? '').toString();
    if (id.isNotEmpty) showMiniProfileSheet(context, id);
  }

  // ---------- 화면 ----------
  @override
  Widget build(BuildContext context) {
    final post = _post;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _close();
      },
      child: Scaffold(
        backgroundColor: kCommunityBg,
        appBar: AppBar(
          backgroundColor: kCommunityBg,
          foregroundColor: Colors.white,
          title: const Text('이야기 보기'),
          actions: [
            if (post != null && post['is_mine'] == true)
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert),
                color: kCommunityCard,
                onSelected: (value) {
                  if (value == 'edit') _edit();
                  if (value == 'delete') _delete();
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(
                      value: 'edit',
                      child: Text('수정', style: TextStyle(color: Colors.white))),
                  PopupMenuItem(
                      value: 'delete',
                      child: Text('삭제', style: TextStyle(color: Colors.redAccent))),
                ],
              )
            else if (post != null)
              IconButton(
                tooltip: post['reported'] == true ? '이미 신고했어요' : '신고하기',
                icon: Icon(Icons.report,
                    color: post['reported'] == true ? Colors.white24 : Colors.redAccent),
                onPressed: post['reported'] == true ? null : _report,
              ),
          ],
        ),
        body: _body(),
        bottomNavigationBar: post == null ? null : _commentInput(),
      ),
    );
  }

  Widget _body() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: Colors.purpleAccent));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!, style: const TextStyle(color: Colors.white70)),
            TextButton(
              onPressed: _load,
              child: const Text('다시 불러오기', style: TextStyle(color: Colors.purpleAccent)),
            ),
          ],
        ),
      );
    }
    final post = _post!;
    final author = (post['author'] as Map?)?.cast<String, dynamic>();
    final genre = (post['genre'] ?? '').toString();
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      children: [
        if (genre.isNotEmpty) Align(alignment: Alignment.centerLeft, child: GenreChip(genre)),
        const SizedBox(height: 12),
        Text(post['title'] ?? '',
            style: const TextStyle(
                color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        // 작성자 이름/사진을 누르면 미니 프로필
        InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => _openProfile(author),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                AuthorAvatar(author: author, radius: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(author?['nickname'] ?? '친구',
                          style: const TextStyle(
                              color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(height: 2),
                      Text(communityDate(post['created_at']),
                          style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            color: kCommunityCard,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: Colors.white10),
          ),
          child: SelectableText(
            post['content'] ?? '',
            style: const TextStyle(color: Colors.white, fontSize: 17, height: 1.8),
          ),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: _actionButton(
                icon: post['liked'] == true ? Icons.favorite : Icons.favorite_border,
                color: Colors.pinkAccent,
                label: '좋아요 ${post['likes_count'] ?? 0}',
                active: post['liked'] == true,
                onPressed: _toggleLike,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _actionButton(
                icon: post['scrapped'] == true ? Icons.bookmark : Icons.bookmark_border,
                color: Colors.amberAccent,
                label: post['scrapped'] == true ? '스크랩됨' : '스크랩',
                active: post['scrapped'] == true,
                onPressed: _toggleScrap,
              ),
            ),
          ],
        ),
        const SizedBox(height: 28),
        Text('댓글 ${post['comments_count'] ?? 0}',
            style: const TextStyle(
                color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        if (_comments.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Center(
              child: Text('첫 번째 댓글을 남겨 볼까요? 💬',
                  style: TextStyle(color: Colors.white38)),
            ),
          ),
        ..._comments.map(_commentTile),
      ],
    );
  }

  Widget _actionButton({
    required IconData icon,
    required Color color,
    required String label,
    required bool active,
    required VoidCallback onPressed,
  }) {
    return OutlinedButton.icon(
      style: OutlinedButton.styleFrom(
        foregroundColor: active ? color : Colors.white70,
        backgroundColor: active ? color.withOpacity(0.12) : Colors.transparent,
        side: BorderSide(color: active ? color : Colors.white24),
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      onPressed: onPressed,
      icon: Icon(icon, color: color),
      label: Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
    );
  }

  Widget _commentTile(Map<String, dynamic> comment) {
    final author = (comment['author'] as Map?)?.cast<String, dynamic>();
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.fromLTRB(14, 12, 4, 12),
      decoration: BoxDecoration(
        color: kCommunityCard,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GestureDetector(
            onTap: () => _openProfile(author),
            child: AuthorAvatar(author: author, radius: 15),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: GestureDetector(
                        onTap: () => _openProfile(author),
                        child: Text(author?['nickname'] ?? '친구',
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: Colors.white, fontWeight: FontWeight.bold)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(communityDate(comment['created_at']),
                        style: const TextStyle(color: Colors.white38, fontSize: 11)),
                  ],
                ),
                const SizedBox(height: 4),
                Text(comment['content'] ?? '',
                    style: const TextStyle(color: Colors.white70, height: 1.4)),
              ],
            ),
          ),
          if (comment['is_mine'] == true)
            IconButton(
              tooltip: '댓글 삭제',
              icon: const Icon(Icons.delete_outline, color: Colors.white38, size: 20),
              onPressed: () => _deleteComment(comment),
            )
          else
            IconButton(
              tooltip: comment['reported'] == true ? '이미 신고했어요' : '댓글 신고',
              icon: Icon(Icons.report_outlined,
                  color: comment['reported'] == true ? Colors.white12 : Colors.white38,
                  size: 20),
              onPressed: comment['reported'] == true ? null : () => _reportComment(comment),
            ),
        ],
      ),
    );
  }

  Widget _commentInput() {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
            16, 8, 8, 8 + MediaQuery.of(context).viewInsets.bottom),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _commentController,
                maxLength: 300,
                minLines: 1,
                maxLines: 3,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _sendComment(),
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  counterText: '',
                  hintText: '다정한 댓글을 남겨 주세요',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF1A0B3A),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(20),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 6),
            IconButton(
              onPressed: _sendingComment ? null : _sendComment,
              icon: _sendingComment
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.purpleAccent))
                  : const Icon(Icons.send_rounded, color: Colors.purpleAccent),
            ),
          ],
        ),
      ),
    );
  }
}
