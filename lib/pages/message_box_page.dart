import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../widgets/message_compose_sheet.dart';
import '../widgets/mini_profile_sheet.dart';
import '../widgets/post_card.dart';
import '../widgets/report_sheet.dart';

/// 마이페이지 > 쪽지함: 받은 쪽지 / 보낸 쪽지
class MessageBoxPage extends StatefulWidget {
  const MessageBoxPage({super.key});

  @override
  State<MessageBoxPage> createState() => _MessageBoxPageState();
}

class _MessageBoxPageState extends State<MessageBoxPage> {
  int _unread = 0;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        backgroundColor: kCommunityBg,
        appBar: AppBar(
          backgroundColor: kCommunityBg,
          foregroundColor: Colors.white,
          title: const Text('쪽지함'),
          bottom: TabBar(
            indicatorColor: Colors.purpleAccent,
            labelColor: Colors.white,
            unselectedLabelColor: Colors.white54,
            labelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
            tabs: [
              Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('받은 쪽지'),
                    if (_unread > 0) ...[
                      const SizedBox(width: 6),
                      UnreadBadge(count: _unread),
                    ],
                  ],
                ),
              ),
              const Tab(text: '보낸 쪽지'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _MessageList(
              box: 'received',
              onUnreadChanged: (n) {
                if (mounted && n != _unread) setState(() => _unread = n);
              },
            ),
            _MessageList(
              box: 'sent',
              onUnreadChanged: (n) {
                if (mounted && n != _unread) setState(() => _unread = n);
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// 안 읽은 쪽지 개수 배지 (마이페이지 메뉴에서도 사용)
class UnreadBadge extends StatelessWidget {
  final int count;

  const UnreadBadge({super.key, required this.count});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      constraints: const BoxConstraints(minWidth: 20),
      decoration: BoxDecoration(
        color: Colors.pinkAccent,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        count > 99 ? '99+' : '$count',
        textAlign: TextAlign.center,
        style: const TextStyle(
            color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
      ),
    );
  }
}

class _MessageList extends StatefulWidget {
  final String box; // received | sent
  final ValueChanged<int> onUnreadChanged;

  const _MessageList({required this.box, required this.onUnreadChanged});

  @override
  State<_MessageList> createState() => _MessageListState();
}

class _MessageListState extends State<_MessageList>
    with AutomaticKeepAliveClientMixin {
  static const _pageSize = 20;

  final List<Map<String, dynamic>> _items = [];
  int _page = 1;
  bool _hasMore = false;
  bool _isLoading = true;
  bool _loadingMore = false;
  String? _error;

  bool get _received => widget.box == 'received';

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _load({bool more = false}) async {
    if (more) {
      if (_loadingMore || !_hasMore) return;
      setState(() => _loadingMore = true);
    } else {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }
    final page = more ? _page + 1 : 1;
    try {
      final response = await ApiClient.get(
          '/api/messages?box=${widget.box}&page=$page&size=$_pageSize');
      if (!mounted) return;
      if (response.statusCode != 200) {
        setState(() {
          if (!more) _error = ApiClient.errorMessage(response);
          _isLoading = false;
          _loadingMore = false;
        });
        return;
      }
      final data = ApiClient.decode(response);
      final items = (data['items'] as List).cast<Map<String, dynamic>>();
      setState(() {
        if (!more) _items.clear();
        _items.addAll(items);
        _page = page;
        _hasMore = data['has_more'] == true;
        _isLoading = false;
        _loadingMore = false;
      });
      widget.onUnreadChanged(data['unread_count'] ?? 0);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        if (!more) _error = '서버에 연결하지 못했어요.';
        _isLoading = false;
        _loadingMore = false;
      });
    }
  }

  Future<void> _refreshUnread() async {
    try {
      final response = await ApiClient.get('/api/messages/unread-count');
      if (response.statusCode == 200) {
        widget.onUnreadChanged(ApiClient.decode(response)['count'] ?? 0);
      }
    } catch (_) {}
  }

  // 쪽지 열기 (받은 쪽지면 서버에서 읽음 처리)
  Future<void> _open(Map<String, dynamic> message) async {
    if (_received && message['is_read'] != true) {
      try {
        final response = await ApiClient.get('/api/messages/${message['id']}');
        if (response.statusCode == 200 && mounted) {
          setState(() => message['is_read'] = true);
          _refreshUnread();
        }
      } catch (_) {}
    }
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: kCommunityCard,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (sheetContext) => _detailSheet(sheetContext, message),
    );
  }

  Future<void> _reply(Map<String, dynamic> message) async {
    await showMessageComposeSheet(
      context,
      receiver: Map<String, dynamic>.from(message['other'] ?? {}),
      replyTo: message['id'],
    );
  }

  Future<void> _delete(Map<String, dynamic> message) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: kCommunityCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Colors.white10),
        ),
        title: const Text('쪽지를 지울까요?',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: const Text('내 쪽지함에서만 지워져요.',
            style: TextStyle(color: Colors.white70)),
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
      final response = await ApiClient.delete('/api/messages/${message['id']}');
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() => _items.removeWhere((m) => m['id'] == message['id']));
        _toast('쪽지를 지웠어요.');
        _refreshUnread();
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
  }

  Future<void> _report(Map<String, dynamic> message) async {
    final reported = await showReportSheet(context,
        target: ReportTarget.message, targetId: message['id']);
    if (reported && mounted) setState(() => message['reported'] = true);
  }

  // ---------- 화면 ----------
  @override
  Widget build(BuildContext context) {
    super.build(context);
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
    if (_items.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          children: [
            const SizedBox(height: 120),
            Center(
              child: Text(
                _received ? '아직 받은 쪽지가 없어요 💌' : '아직 보낸 쪽지가 없어요.\n친구 프로필에서 쪽지를 보내 보세요!',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white54, height: 1.6),
              ),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _items.length + (_hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == _items.length) {
            return Center(
              child: _loadingMore
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: CircularProgressIndicator(color: Colors.purpleAccent),
                    )
                  : TextButton(
                      onPressed: () => _load(more: true),
                      child: const Text('더보기', style: TextStyle(color: Colors.purpleAccent)),
                    ),
            );
          }
          return _tile(_items[index]);
        },
      ),
    );
  }

  Widget _tile(Map<String, dynamic> message) {
    final other = (message['other'] as Map?)?.cast<String, dynamic>();
    final unread = _received && message['is_read'] != true;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: unread ? kCommunityPurple.withOpacity(0.14) : kCommunityCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: unread ? kCommunityPurple : Colors.white10),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () => _open(message),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AuthorAvatar(author: other, radius: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            _received
                                ? (other?['nickname'] ?? '친구')
                                : '받는 친구: ${other?['nickname'] ?? '친구'}',
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                        ),
                        if (unread) ...[
                          const SizedBox(width: 6),
                          const Icon(Icons.circle, color: Colors.pinkAccent, size: 8),
                        ],
                        const Spacer(),
                        Text(communityDate(message['created_at']),
                            style: const TextStyle(color: Colors.white38, fontSize: 12)),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      message['content'] ?? '',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white70, height: 1.4),
                    ),
                    if (!_received)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          message['is_read'] == true ? '읽음' : '아직 안 읽음',
                          style: TextStyle(
                              color: message['is_read'] == true
                                  ? Colors.greenAccent
                                  : Colors.white38,
                              fontSize: 12),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _detailSheet(BuildContext sheetContext, Map<String, dynamic> message) {
    final other = (message['other'] as Map?)?.cast<String, dynamic>();
    final reported = message['reported'] == true;

    void closeThen(Future<void> Function() action) {
      Navigator.pop(sheetContext);
      action();
    }

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 18),
            InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: other?['id'] == null
                  ? null
                  : () => closeThen(() => showMiniProfileSheet(context, other!['id'])),
              child: Row(
                children: [
                  AuthorAvatar(author: other, radius: 22),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _received
                              ? '${other?['nickname'] ?? '친구'}이(가) 보낸 쪽지'
                              : '${other?['nickname'] ?? '친구'}에게 보낸 쪽지',
                          style: const TextStyle(
                              color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold),
                        ),
                        Text(communityDate(message['created_at']),
                            style: const TextStyle(color: Colors.white38, fontSize: 12)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              constraints: BoxConstraints(
                  maxHeight: MediaQuery.of(sheetContext).size.height * 0.4),
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFF1A0B3A),
                borderRadius: BorderRadius.circular(18),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  message['content'] ?? '',
                  style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.6),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                if (_received) ...[
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: kCommunityPurple,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      ),
                      onPressed: () => closeThen(() => _reply(message)),
                      icon: const Icon(Icons.reply),
                      label: const Text('답장', style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(width: 8),
                ],
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white70,
                      side: const BorderSide(color: Colors.white24),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    onPressed: () => closeThen(() => _delete(message)),
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('삭제'),
                  ),
                ),
                if (_received) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.redAccent,
                        side: BorderSide(
                            color: reported ? Colors.white12 : Colors.redAccent),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      ),
                      onPressed: reported ? null : () => closeThen(() => _report(message)),
                      icon: const Icon(Icons.report_outlined),
                      label: Text(reported ? '신고함' : '신고'),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
