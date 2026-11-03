import 'package:flutter/material.dart';

import '../core/api_client.dart';
import 'post_card.dart';
import 'report_sheet.dart';

/// 쪽지 쓰기 창 (아래에서 올라옴). 보내면 true.
/// [replyTo]: 답장이면 원래 받은 쪽지 id
Future<bool> showMessageComposeSheet(
  BuildContext context, {
  required Map<String, dynamic> receiver, // {id, nickname, profile_image_url}
  String replyTo = '',
}) async {
  final result = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: kCommunityCard,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
    ),
    builder: (_) => _ComposeSheet(receiver: receiver, replyTo: replyTo),
  );
  return result == true;
}

class _ComposeSheet extends StatefulWidget {
  final Map<String, dynamic> receiver;
  final String replyTo;

  const _ComposeSheet({required this.receiver, required this.replyTo});

  @override
  State<_ComposeSheet> createState() => _ComposeSheetState();
}

class _ComposeSheetState extends State<_ComposeSheet> {
  final TextEditingController _controller = TextEditingController();
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final content = _controller.text.trim();
    if (content.isEmpty) {
      setState(() => _error = '쪽지 내용을 적어 주세요.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    final messenger = ScaffoldMessenger.of(context);
    try {
      final response = await ApiClient.post('/api/messages', body: {
        'receiver_id': widget.receiver['id'],
        'content': content,
        'reply_to': widget.replyTo,
      });
      if (!mounted) return;
      if (response.statusCode == 200) {
        Navigator.pop(context, true);
        messenger.showSnackBar(const SnackBar(content: Text('쪽지를 보냈어요! 💌')));
        return;
      }
      setState(() {
        _error = ApiClient.errorMessage(response);
        _sending = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = '서버에 연결하지 못했어요.';
        _sending = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final nickname = (widget.receiver['nickname'] ?? '친구').toString();
    return Padding(
      padding: EdgeInsets.fromLTRB(
          24, 12, 24, 24 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SheetHandle(),
          const SizedBox(height: 16),
          Row(
            children: [
              AuthorAvatar(author: widget.receiver, radius: 18),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  widget.replyTo.isEmpty ? '$nickname에게 쪽지 쓰기' : '$nickname에게 답장하기',
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            maxLength: 300,
            minLines: 4,
            maxLines: 6,
            autofocus: true,
            style: const TextStyle(color: Colors.white, height: 1.5),
            decoration: InputDecoration(
              hintText: '다정한 말로 적어 주세요',
              hintStyle: const TextStyle(color: Colors.white38),
              counterStyle: const TextStyle(color: Colors.white38),
              filled: true,
              fillColor: const Color(0xFF1A0B3A),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
            ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: kCommunityPurple,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              onPressed: _sending ? null : _send,
              icon: _sending
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.send_rounded),
              label: const Text('보내기', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }
}
