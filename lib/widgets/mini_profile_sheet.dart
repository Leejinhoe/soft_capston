import 'package:flutter/material.dart';

import '../core/api_client.dart';
import 'message_compose_sheet.dart';
import 'post_card.dart';
import 'report_sheet.dart';

/// 작성자 미니 프로필 (아래에서 올라옴): 사진, 닉네임, 한 줄 소개, 공개한 동화 수, 받은 좋아요 수
/// 내 프로필이면 "쪽지 보내기", "신고하기" 버튼을 숨깁니다.
Future<void> showMiniProfileSheet(BuildContext context, String userId) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: kCommunityCard,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
    ),
    builder: (_) => _MiniProfileSheet(userId: userId),
  );
}

class _MiniProfileSheet extends StatefulWidget {
  final String userId;

  const _MiniProfileSheet({required this.userId});

  @override
  State<_MiniProfileSheet> createState() => _MiniProfileSheetState();
}

class _MiniProfileSheetState extends State<_MiniProfileSheet> {
  Map<String, dynamic>? _profile;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final response =
          await ApiClient.get('/api/users/${Uri.encodeComponent(widget.userId)}/profile');
      if (!mounted) return;
      setState(() {
        if (response.statusCode == 200) {
          _profile = Map<String, dynamic>.from(ApiClient.decode(response));
        } else {
          _error = ApiClient.errorMessage(response);
        }
      });
    } catch (_) {
      if (mounted) setState(() => _error = '서버에 연결하지 못했어요.');
    }
  }

  Future<void> _sendMessage() async {
    final profile = _profile!;
    final navigator = Navigator.of(context);
    final rootContext = navigator.context;
    navigator.pop();
    await showMessageComposeSheet(rootContext, receiver: profile);
  }

  Future<void> _report() async {
    final navigator = Navigator.of(context);
    final rootContext = navigator.context;
    navigator.pop();
    await showReportSheet(rootContext, target: ReportTarget.user, targetId: widget.userId);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SheetHandle(),
            const SizedBox(height: 20),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 32),
                child: Text(_error!, style: const TextStyle(color: Colors.white70)),
              )
            else if (_profile == null)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: CircularProgressIndicator(color: Colors.purpleAccent),
              )
            else
              ..._content(_profile!),
          ],
        ),
      ),
    );
  }

  List<Widget> _content(Map<String, dynamic> p) {
    final isMe = p['is_me'] == true;
    return [
      AuthorAvatar(author: p, radius: 40),
      const SizedBox(height: 14),
      Text(p['nickname'] ?? '친구',
          style: const TextStyle(
              color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
      const SizedBox(height: 6),
      Text(p['bio'] ?? '',
          textAlign: TextAlign.center,
          style: const TextStyle(color: Colors.white70, fontSize: 15)),
      const SizedBox(height: 20),
      Row(
        children: [
          Expanded(
            child: _stat(Icons.auto_stories, '공개한 동화', '${p['public_story_count'] ?? 0}편'),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _stat(Icons.favorite, '받은 좋아요', '${p['received_likes'] ?? 0}개'),
          ),
        ],
      ),
      if (!isMe) ...[
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: kCommunityPurple,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: _sendMessage,
                icon: const Icon(Icons.mail_outline),
                label: const Text('쪽지 보내기', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
            const SizedBox(width: 12),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.redAccent,
                side: const BorderSide(color: Colors.redAccent),
                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 18),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              onPressed: _report,
              icon: const Icon(Icons.report_outlined),
              label: const Text('신고하기'),
            ),
          ],
        ),
      ],
    ];
  }

  Widget _stat(IconData icon, String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14),
      decoration: BoxDecoration(
        color: Colors.purple.withOpacity(0.15),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        children: [
          Icon(icon, color: Colors.purpleAccent),
          const SizedBox(height: 6),
          Text(value,
              style: const TextStyle(
                  color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
        ],
      ),
    );
  }
}
