import 'package:flutter/material.dart';

import '../core/api_client.dart';
import 'post_card.dart';

/// 신고 대상 종류 (서버 target_type과 같은 값)
enum ReportTarget { post, comment, user, message }

const _targetLabels = {
  ReportTarget.post: '게시글',
  ReportTarget.comment: '댓글',
  ReportTarget.user: '친구',
  ReportTarget.message: '쪽지',
};

/// 신고 사유 (서버 reason 코드 → 화면 문구)
const reportReasons = [
  ('abuse', '욕설/비방'),
  ('inappropriate', '부적절한 내용'),
  ('spam', '도배/광고'),
  ('other', '기타'),
];

/// 아래에서 올라오는 신고 창. 신고가 접수되었거나 이미 신고한 대상이면 true를 돌려줍니다.
Future<bool> showReportSheet(
  BuildContext context, {
  required ReportTarget target,
  required String targetId,
}) async {
  final result = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: kCommunityCard,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
    ),
    builder: (_) => _ReportSheet(target: target, targetId: targetId),
  );
  return result == true;
}

class _ReportSheet extends StatefulWidget {
  final ReportTarget target;
  final String targetId;

  const _ReportSheet({required this.target, required this.targetId});

  @override
  State<_ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends State<_ReportSheet> {
  final TextEditingController _detail = TextEditingController();
  String? _reason;
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _detail.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final detail = _detail.text.trim();
    if (_reason == null) {
      setState(() => _error = '신고하는 까닭을 골라 주세요.');
      return;
    }
    if (_reason == 'other' && detail.isEmpty) {
      setState(() => _error = '어떤 일인지 짧게 적어 주세요.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    final messenger = ScaffoldMessenger.of(context);
    try {
      final response = await ApiClient.post('/api/reports', body: {
        'target_type': widget.target.name,
        'target_id': widget.targetId,
        'reason': _reason,
        'detail': detail,
      });
      if (!mounted) return;
      if (response.statusCode == 200 || response.statusCode == 409) {
        Navigator.pop(context, true);
        messenger.showSnackBar(SnackBar(
          content: Text(ApiClient.errorMessage(response, '신고가 접수되었어요.')),
        ));
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
    final label = _targetLabels[widget.target]!;
    return Padding(
      padding: EdgeInsets.fromLTRB(
          24, 12, 24, 24 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SheetHandle(),
            const SizedBox(height: 16),
            Text('🚨 $label 신고하기',
                style: const TextStyle(
                    color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            const Text('왜 신고하는지 알려 주면 어른들이 확인할게요.',
                style: TextStyle(color: Colors.white54)),
            const SizedBox(height: 16),
            ...reportReasons.map((r) => _reasonTile(r.$1, r.$2)),
            if (_reason == 'other') ...[
              const SizedBox(height: 6),
              TextField(
                controller: _detail,
                maxLength: 200,
                maxLines: 3,
                minLines: 2,
                autofocus: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '어떤 일이 있었는지 적어 주세요',
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
            ],
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
              ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.redAccent,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: _sending ? null : _submit,
                child: _sending
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('신고하기', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _reasonTile(String code, String text) {
    final selected = _reason == code;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => setState(() {
          _reason = code;
          _error = null;
        }),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: selected ? kCommunityPurple.withOpacity(0.18) : Colors.transparent,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: selected ? kCommunityPurple : Colors.white12),
          ),
          child: Row(
            children: [
              Icon(selected ? Icons.radio_button_checked : Icons.radio_button_off,
                  color: selected ? Colors.purpleAccent : Colors.white38),
              const SizedBox(width: 12),
              Text(text,
                  style: TextStyle(
                      color: selected ? Colors.white : Colors.white70,
                      fontWeight: selected ? FontWeight.bold : FontWeight.normal)),
            ],
          ),
        ),
      ),
    );
  }
}

/// 바텀시트 맨 위 손잡이
class SheetHandle extends StatelessWidget {
  const SheetHandle({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        decoration: BoxDecoration(
          color: Colors.white24,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
