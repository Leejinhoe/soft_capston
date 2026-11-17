import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'services/db_service.dart';

Future<void> showCommunityReportSheet(
  BuildContext context, {
  required String targetType,
  required String targetId,
  required String? accountId,
  String? postId,
}) async {
  if (accountId == null || accountId.trim().isEmpty) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('신고하려면 로그인해 주세요.')));
    return;
  }
  final message = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.pageSurface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
    ),
    builder: (_) => _ReportSheet(
      targetType: targetType,
      targetId: targetId,
      accountId: accountId,
      postId: postId,
    ),
  );
  if (context.mounted && message != null) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

class _ReportSheet extends StatefulWidget {
  const _ReportSheet({
    required this.targetType,
    required this.targetId,
    required this.accountId,
    this.postId,
  });

  final String targetType;
  final String targetId;
  final String accountId;
  final String? postId;

  @override
  State<_ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends State<_ReportSheet> {
  final _details = TextEditingController();
  String? _reason;
  bool _sending = false;

  @override
  void dispose() {
    _details.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_reason == null) return;
    if (_reason == '기타' && _details.text.trim().isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('신고 내용을 입력해 주세요.')));
      return;
    }
    setState(() => _sending = true);
    try {
      final result = await DbService.createCommunityReport(
        targetType: widget.targetType,
        targetId: widget.targetId,
        reporterAccountId: widget.accountId,
        postId: widget.postId,
        reason: _reason!,
        details: _details.text,
      );
      if (mounted) {
        Navigator.pop(
          context,
          result.message.isNotEmpty ? result.message : '신고가 접수되었어요.',
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '신고 실패: ${error.toString().replaceFirst('Exception: ', '')}',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          24,
          24,
          24,
          24 + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.targetType == 'comment' ? '댓글 신고하기' : '게시글 신고하기',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 21,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              '신고 사유를 선택해 주세요.',
              style: TextStyle(color: Colors.white70),
            ),
            const SizedBox(height: 12),
            for (final reason in const ['욕설/비방', '부적절한 내용', '도배/광고', '기타'])
              ListTile(
                onTap: _sending ? null : () => setState(() => _reason = reason),
                leading: Icon(
                  _reason == reason
                      ? Icons.radio_button_checked
                      : Icons.radio_button_off,
                  color: _reason == reason ? AppColors.p400 : Colors.white54,
                ),
                title: Text(
                  reason,
                  style: const TextStyle(color: Colors.white),
                ),
                contentPadding: EdgeInsets.zero,
              ),
            TextField(
              controller: _details,
              maxLength: 500,
              maxLines: 3,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(hintText: '상세 내용 (선택, 기타는 필수)'),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _sending || _reason == null ? null : _submit,
                child: Text(_sending ? '접수 중...' : '신고하기'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
