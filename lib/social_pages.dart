import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_theme.dart';
import 'community_page.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/db_service.dart';

String _socialDate(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '');
  if (date == null) return '';
  final local = date.isUtc ? date.toLocal() : date;
  return '${local.year}.${local.month.toString().padLeft(2, '0')}.${local.day.toString().padLeft(2, '0')}';
}

String _socialInitial(String name) =>
    name.trim().isEmpty ? '?' : name.trim()[0];

class _SocialAvatar extends StatelessWidget {
  final String name;
  final String? imageUrl;
  final double radius;

  const _SocialAvatar({required this.name, this.imageUrl, this.radius = 22});

  @override
  Widget build(BuildContext context) {
    final resolved = DbService.resolveMediaUrl(imageUrl);
    return CircleAvatar(
      radius: radius,
      backgroundColor: AppColors.p600.withValues(alpha: 0.42),
      backgroundImage: resolved == null
          ? null
          : NetworkImage(resolved, headers: DbService.mediaHeaders),
      child: resolved == null
          ? Text(
              _socialInitial(name),
              style: TextStyle(
                color: Colors.white,
                fontSize: radius * 0.9,
                fontWeight: FontWeight.w800,
              ),
            )
          : null,
    );
  }
}

Future<void> showPublicProfile(BuildContext context, String? userId) async {
  final id = userId?.trim() ?? '';
  if (id.isEmpty) return;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.pageSurface,
    builder: (_) => _PublicProfileSheet(userId: id),
  );
}

class _PublicProfileSheet extends StatelessWidget {
  final String userId;

  const _PublicProfileSheet({required this.userId});

  @override
  Widget build(BuildContext context) => SafeArea(
    child: FutureBuilder<Map<String, dynamic>>(
      future: DbService.fetchPublicProfile(userId),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const SizedBox(
            height: 260,
            child: Center(child: CircularProgressIndicator()),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return SizedBox(
            height: 220,
            child: Center(
              child: Text('프로필을 불러오지 못했어요. ${snapshot.error ?? ''}'),
            ),
          );
        }
        final profile = snapshot.data!;
        final isMe = profile['is_me'] == true;
        final imageUrl = DbService.resolveMediaUrl(
          profile['profile_image_url']?.toString(),
        );
        final nickname = profile['nickname']?.toString() ?? '동화 친구';
        return SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 42,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 18),
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF382077), Color(0xFF791D70)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(26),
                  ),
                  child: Column(
                    children: [
                      _SocialAvatar(
                        name: nickname,
                        imageUrl: imageUrl,
                        radius: 42,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        nickname,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 23,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      if ((profile['bio']?.toString() ?? '').isNotEmpty) ...[
                        const SizedBox(height: 7),
                        Text(
                          profile['bio'].toString(),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white70,
                            height: 1.45,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                _ProfileStatsRow(profile: profile),
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => PublicProfilePage(userId: userId),
                    ),
                  ),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('프로필 전체 보기'),
                ),
                if (!isMe) ...[
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => MessageComposePage(
                            receiverId:
                                profile['account_id']?.toString() ?? userId,
                            receiverName: nickname,
                          ),
                        ),
                      ),
                      icon: const Icon(Icons.mail_outline),
                      label: const Text('쪽지 보내기'),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    ),
  );
}

class PublicProfilePage extends StatelessWidget {
  final String userId;

  const PublicProfilePage({super.key, required this.userId});

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.pageBackground,
    appBar: AppBar(
      title: const Text('프로필'),
      backgroundColor: AppColors.pageBackground,
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      future: DbService.fetchPublicProfile(userId),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done)
          return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError || !snapshot.hasData)
          return Center(child: Text('프로필을 불러오지 못했어요. ${snapshot.error ?? ''}'));
        final profile = snapshot.data!;
        final image = DbService.resolveMediaUrl(
          profile['profile_image_url']?.toString(),
        );
        final nickname = profile['nickname']?.toString() ?? '동화 친구';
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 700),
            child: ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Container(
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(32),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.p700.withValues(alpha: 0.24),
                        blurRadius: 28,
                        offset: const Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      _SocialAvatar(
                        name: nickname,
                        imageUrl: image,
                        radius: 54,
                      ),
                      const SizedBox(height: 18),
                      Text(
                        nickname,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 28,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        (profile['bio']?.toString().isNotEmpty ?? false)
                            ? profile['bio'].toString()
                            : '아직 소개글이 없어요.',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white70,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                _ProfileStatsRow(profile: profile),
                if (profile['is_me'] != true) ...[
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => MessageComposePage(
                          receiverId:
                              profile['account_id']?.toString() ?? userId,
                          receiverName: nickname,
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.mail_outline),
                    label: const Text('쪽지 보내기'),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    ),
  );
}

class _ProfileStat extends StatelessWidget {
  final String label;
  final dynamic value;

  const _ProfileStat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Text(
        '${(value as num?)?.toInt() ?? 0}',
        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(color: Colors.white60, fontSize: 12)),
    ],
  );
}

class _ProfileStatsRow extends StatelessWidget {
  final Map<String, dynamic> profile;

  const _ProfileStatsRow({required this.profile});

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 10),
    decoration: BoxDecoration(
      color: AppColors.pageSurface,
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: AppColors.border),
    ),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        _ProfileStat(label: '공개 동화', value: profile['public_story_count']),
        _ProfileStat(label: '게시글', value: profile['public_post_count']),
        _ProfileStat(label: '받은 좋아요', value: profile['like_count']),
      ],
    ),
  );
}

class _MessageStatusChip extends StatelessWidget {
  final bool isRead;

  const _MessageStatusChip({required this.isRead});

  @override
  Widget build(BuildContext context) {
    final color = isRead ? AppColors.teal : Colors.white54;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        isRead ? '읽음' : '아직 안 읽음',
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class InboxPage extends StatefulWidget {
  const InboxPage({super.key});

  @override
  State<InboxPage> createState() => _InboxPageState();
}

class _InboxPageState extends State<InboxPage> {
  late Future<Map<String, dynamic>> _inbox;

  @override
  void initState() {
    super.initState();
    _inbox = DbService.fetchMyInbox();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => DbService.markInboxRead(),
    );
  }

  Future<void> _refresh() async {
    await DbService.markInboxRead();
    if (mounted) setState(() => _inbox = DbService.fetchMyInbox());
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.pageBackground,
    appBar: AppBar(
      title: const Text(
        '알림·공지함',
        style: TextStyle(fontWeight: FontWeight.w800),
      ),
      backgroundColor: AppColors.pageBackground,
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _inbox,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done)
          return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError)
          return Center(child: Text('알림을 불러오지 못했어요. ${snapshot.error}'));
        final items = (snapshot.data?['items'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .toList();
        if (items.isEmpty) {
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                SizedBox(height: 120),
                Icon(
                  Icons.notifications_none_rounded,
                  size: 48,
                  color: Colors.white24,
                ),
                SizedBox(height: 12),
                Center(
                  child: Text(
                    '아직 새로운 알림이 없어요.\n공지와 계정 안내가 여기에 모여요.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white54, height: 1.6),
                  ),
                ),
              ],
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: _refresh,
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
            itemCount: items.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              final item = items[index];
              final isWarning = item['type'] == 'warning';
              final unread =
                  item['is_unread'] == true ||
                  (isWarning && item['is_read'] != true);
              final color = isWarning ? Colors.orangeAccent : AppColors.p400;
              final body =
                  item['body']?.toString() ?? item['content']?.toString() ?? '';
              return Material(
                color: unread
                    ? color.withValues(alpha: 0.09)
                    : AppColors.pageSurface,
                borderRadius: BorderRadius.circular(22),
                child: InkWell(
                  borderRadius: BorderRadius.circular(22),
                  onTap: () => showDialog<void>(
                    context: context,
                    builder: (_) => AlertDialog(
                      backgroundColor: AppColors.pageSurface,
                      title: Row(
                        children: [
                          Icon(
                            isWarning
                                ? Icons.warning_amber_rounded
                                : Icons.campaign_rounded,
                            color: color,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(item['title']?.toString() ?? '알림'),
                          ),
                        ],
                      ),
                      content: SingleChildScrollView(child: Text(body)),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('닫기'),
                        ),
                      ],
                    ),
                  ),
                  child: Container(
                    padding: const EdgeInsets.all(17),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(
                        color: color.withValues(alpha: unread ? 0.65 : 0.25),
                      ),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Icon(
                            isWarning
                                ? Icons.warning_amber_rounded
                                : Icons.campaign_rounded,
                            color: color,
                          ),
                        ),
                        const SizedBox(width: 13),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  if (unread) ...[
                                    Container(
                                      margin: const EdgeInsets.only(right: 7),
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 7,
                                        vertical: 3,
                                      ),
                                      decoration: BoxDecoration(
                                        color: AppColors.pink,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: const Text(
                                        'NEW',
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontSize: 9,
                                          fontWeight: FontWeight.w900,
                                        ),
                                      ),
                                    ),
                                  ],
                                  Expanded(
                                    child: Text(
                                      item['title']?.toString() ??
                                          (isWarning ? '받은 경고' : '공지사항'),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    _socialDate(item['created_at']),
                                    style: const TextStyle(
                                      color: Colors.white38,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                              if (body.isNotEmpty) ...[
                                const SizedBox(height: 7),
                                Text(
                                  body,
                                  maxLines: 3,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    height: 1.45,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        );
      },
    ),
  );
}

class MessageBoxPage extends StatefulWidget {
  const MessageBoxPage({super.key});

  @override
  State<MessageBoxPage> createState() => _MessageBoxPageState();
}

class _MessageBoxPageState extends State<MessageBoxPage> {
  int _tab = 0;
  int _unreadCount = 0;
  late Future<List<Map<String, dynamic>>> _messages;

  @override
  void initState() {
    super.initState();
    _load();
    _loadUnreadCount();
  }

  Future<void> _loadUnreadCount() async {
    try {
      final count = await DbService.fetchUnreadMessageCount();
      if (mounted) setState(() => _unreadCount = count);
    } catch (_) {}
  }

  void _load() =>
      _messages = DbService.fetchMessages(box: _tab == 0 ? 'received' : 'sent');

  Future<void> _refresh() async {
    setState(_load);
    await _messages;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.pageBackground,
    appBar: AppBar(
      title: const Text('쪽지함', style: TextStyle(fontWeight: FontWeight.w800)),
      backgroundColor: AppColors.pageBackground,
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
          child: Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: AppColors.pageSurface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                _messageTab(0, '받은 쪽지', _unreadCount),
                _messageTab(1, '보낸 쪽지', 0),
              ],
            ),
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _messages,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done)
                return const Center(child: CircularProgressIndicator());
              if (snapshot.hasError)
                return Center(child: Text('쪽지를 불러오지 못했어요. ${snapshot.error}'));
              final messages = snapshot.data ?? const [];
              if (messages.isEmpty)
                return const Center(child: Text('쪽지가 아직 없어요.'));
              return RefreshIndicator(
                onRefresh: _refresh,
                child: ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: messages.length,
                  itemBuilder: (context, index) {
                    final message = messages[index];
                    final received = _tab == 0;
                    final unread = received && message['is_read'] != true;
                    final name = received
                        ? message['sender_name']?.toString() ?? '보낸 사람'
                        : message['receiver_name']?.toString() ?? '받는 사람';
                    final image = received
                        ? message['sender_profile_image_url']?.toString()
                        : message['receiver_profile_image_url']?.toString();
                    return Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: unread
                            ? AppColors.p600.withValues(alpha: 0.14)
                            : AppColors.pageSurface,
                        borderRadius: BorderRadius.circular(22),
                        border: Border.all(
                          color: unread ? AppColors.p400 : AppColors.border,
                        ),
                      ),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(22),
                        onTap: () async {
                          await Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => DirectMessageDetailPage(
                                messageId: message['id'].toString(),
                                sentBox: !received,
                              ),
                            ),
                          );
                          if (mounted) {
                            setState(_load);
                            _loadUnreadCount();
                          }
                        },
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _SocialAvatar(
                                name: name,
                                imageUrl: image,
                                radius: 21,
                              ),
                              const SizedBox(width: 13),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Flexible(
                                          child: Text(
                                            name,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontWeight: FontWeight.w800,
                                            ),
                                          ),
                                        ),
                                        if (unread) ...[
                                          const SizedBox(width: 7),
                                          const Icon(
                                            Icons.circle,
                                            color: AppColors.pink,
                                            size: 8,
                                          ),
                                        ],
                                        const Spacer(),
                                        Text(
                                          _socialDate(message['created_at']),
                                          style: const TextStyle(
                                            color: Colors.white38,
                                            fontSize: 11,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 7),
                                    Text(
                                      message['content']?.toString() ?? '',
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        color: Colors.white70,
                                        height: 1.45,
                                      ),
                                    ),
                                    if (!received) ...[
                                      const SizedBox(height: 8),
                                      _MessageStatusChip(
                                        isRead: message['is_read'] == true,
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
              );
            },
          ),
        ),
      ],
    ),
  );

  Widget _messageTab(int index, String label, int badge) {
    final selected = _tab == index;
    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () {
          if (_tab == index) return;
          setState(() {
            _tab = index;
            _load();
          });
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: selected ? AppColors.p600 : Colors.transparent,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                label,
                style: TextStyle(
                  color: selected ? Colors.white : Colors.white60,
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (badge > 0 && index == 0) ...[
                const SizedBox(width: 7),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 7,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.pink,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    badge > 99 ? '99+' : '$badge',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class DirectMessageDetailPage extends StatefulWidget {
  final String messageId;
  final bool sentBox;

  const DirectMessageDetailPage({
    super.key,
    required this.messageId,
    required this.sentBox,
  });

  @override
  State<DirectMessageDetailPage> createState() =>
      _DirectMessageDetailPageState();
}

class _DirectMessageDetailPageState extends State<DirectMessageDetailPage> {
  late Future<Map<String, dynamic>> _message;

  @override
  void initState() {
    super.initState();
    _message = DbService.fetchMessage(widget.messageId);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.pageBackground,
    appBar: AppBar(
      title: const Text('쪽지'),
      backgroundColor: AppColors.pageBackground,
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _message,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done)
          return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError || !snapshot.hasData)
          return Center(child: Text('쪽지를 열지 못했어요. ${snapshot.error ?? ''}'));
        final message = snapshot.data!;
        final state = context.read<AppState>();
        final otherId = widget.sentBox
            ? message['receiver_id']
            : message['sender_id'];
        final otherName = widget.sentBox
            ? message['receiver_name']
            : message['sender_name'];
        final otherNameText = otherName?.toString() ?? '동화 친구';
        final otherImage = widget.sentBox
            ? message['receiver_profile_image_url']?.toString()
            : message['sender_profile_image_url']?.toString();
        final canReply =
            !widget.sentBox && message['sender_id'] != state.currentAccountId;
        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF382077), Color(0xFF791D70)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  _SocialAvatar(
                    name: otherNameText,
                    imageUrl: otherImage,
                    radius: 25,
                  ),
                  const SizedBox(width: 13),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.sentBox
                              ? '$otherNameText에게 보낸 쪽지'
                              : '$otherNameText이(가) 보낸 쪽지',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          _socialDate(message['created_at']),
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: '프로필 보기',
                    onPressed: otherId == null
                        ? null
                        : () => showPublicProfile(context, otherId.toString()),
                    icon: const Icon(
                      Icons.person_outline_rounded,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            Container(
              constraints: const BoxConstraints(minHeight: 210),
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: AppColors.pageSurface,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: AppColors.border),
              ),
              child: SelectableText(
                message['content']?.toString() ?? '',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 17,
                  height: 1.75,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(15),
              decoration: BoxDecoration(
                color: AppColors.pageSurface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  Icon(
                    widget.sentBox && message['is_read'] != true
                        ? Icons.mark_email_unread_outlined
                        : Icons.mark_email_read_outlined,
                    color: widget.sentBox && message['is_read'] != true
                        ? Colors.white54
                        : AppColors.teal,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      widget.sentBox
                          ? (message['is_read'] == true
                                ? '상대방이 쪽지를 읽었어요.'
                                : '아직 읽지 않았어요.')
                          : '읽음으로 표시되었어요.',
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ),
                  if (widget.sentBox)
                    _MessageStatusChip(isRead: message['is_read'] == true),
                ],
              ),
            ),
            if (canReply) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => MessageComposePage(
                        receiverId: otherId.toString(),
                        receiverName: otherNameText,
                        replyTo: widget.messageId,
                      ),
                    ),
                  ),
                  icon: const Icon(Icons.reply_rounded),
                  label: const Text('답장하기'),
                ),
              ),
            ],
          ],
        );
      },
    ),
  );
}

class MessageComposePage extends StatefulWidget {
  final String receiverId;
  final String receiverName;
  final String? replyTo;

  const MessageComposePage({
    super.key,
    required this.receiverId,
    required this.receiverName,
    this.replyTo,
  });

  @override
  State<MessageComposePage> createState() => _MessageComposePageState();
}

class _MessageComposePageState extends State<MessageComposePage> {
  final _controller = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (_controller.text.trim().isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      await DbService.sendMessage(
        receiverId: widget.receiverId,
        content: _controller.text,
        replyTo: widget.replyTo,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('쪽지를 보냈어요.')));
      Navigator.pop(context, true);
    } catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', '')),
          ),
        );
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.pageBackground,
    appBar: AppBar(
      title: const Text('쪽지 쓰기', style: TextStyle(fontWeight: FontWeight.w800)),
      backgroundColor: AppColors.pageBackground,
    ),
    body: Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
      child: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF382077), Color(0xFF791D70)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(22),
            ),
            child: Row(
              children: [
                _SocialAvatar(name: widget.receiverName, radius: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '받는 사람',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        widget.receiverName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 17,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.mail_outline_rounded, color: Colors.white70),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Expanded(
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              decoration: BoxDecoration(
                color: AppColors.pageSurface,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: AppColors.border),
              ),
              child: TextField(
                controller: _controller,
                maxLength: 300,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                style: const TextStyle(color: Colors.white, height: 1.6),
                decoration: const InputDecoration(
                  hintText: '마음을 담아 쪽지를 써 보세요.',
                  border: InputBorder.none,
                  counterStyle: TextStyle(color: Colors.white38),
                ),
              ),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _sending ? null : _send,
              icon: const Icon(Icons.send),
              label: Text(_sending ? '보내는 중...' : '쪽지 보내기'),
            ),
          ),
        ],
      ),
    ),
  );
}

class ScrapListPage extends StatefulWidget {
  const ScrapListPage({super.key});

  @override
  State<ScrapListPage> createState() => _ScrapListPageState();
}

class _ScrapListPageState extends State<ScrapListPage> {
  late Future<List<CommunityPost>> _posts;

  @override
  void initState() {
    super.initState();
    _posts = DbService.fetchMyScraps();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.pageBackground,
    appBar: AppBar(
      title: const Text('스크랩한 게시글'),
      backgroundColor: AppColors.pageBackground,
    ),
    body: FutureBuilder<List<CommunityPost>>(
      future: _posts,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done)
          return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError)
          return Center(child: Text('스크랩 목록을 불러오지 못했어요. ${snapshot.error}'));
        final posts = snapshot.data ?? const [];
        if (posts.isEmpty) {
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            children: const [
              SizedBox(height: 110),
              Icon(
                Icons.bookmark_border_rounded,
                size: 54,
                color: Colors.white24,
              ),
              SizedBox(height: 14),
              Center(
                child: Text(
                  '아직 스크랩한 글이 없어요.\n마음에 드는 이야기를 저장해 보세요.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white54, height: 1.6),
                ),
              ),
            ],
          );
        }
        return ListView.builder(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
          itemCount: posts.length,
          itemBuilder: (context, index) {
            final post = posts[index];
            return Container(
              margin: const EdgeInsets.only(bottom: 14),
              decoration: BoxDecoration(
                color: AppColors.pageSurface,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: AppColors.border),
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(24),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => CommunityPostDetailPage(initialPost: post),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(17),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          _SocialAvatar(
                            name: post.authorName,
                            imageUrl: post.authorProfileImageUrl,
                            radius: 18,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              post.authorName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          Text(
                            _socialDate(post.createdAt.toIso8601String()),
                            style: const TextStyle(
                              color: Colors.white38,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 52,
                            height: 52,
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(
                                colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                              ),
                              borderRadius: BorderRadius.circular(17),
                            ),
                            child: Text(
                              post.storyEmoji,
                              style: const TextStyle(fontSize: 28),
                            ),
                          ),
                          const SizedBox(width: 13),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  post.title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 18,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  post.preview,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: Colors.white60,
                                    height: 1.4,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 5,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.p600.withValues(alpha: 0.18),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              '#${post.genre}',
                              style: const TextStyle(
                                color: AppColors.p300,
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          const Spacer(),
                          const Icon(
                            Icons.favorite_rounded,
                            color: AppColors.pink2,
                            size: 16,
                          ),
                          const SizedBox(width: 5),
                          Text(
                            '${post.likeCount}',
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(width: 14),
                          const Icon(
                            Icons.chat_bubble_rounded,
                            color: Colors.lightBlueAccent,
                            size: 15,
                          ),
                          const SizedBox(width: 5),
                          Text(
                            '${post.commentCount}',
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Icon(
                            Icons.bookmark_rounded,
                            color: AppColors.p400,
                            size: 19,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    ),
  );
}
