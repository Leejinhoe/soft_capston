import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 정지된 계정으로 로그인했을 때 보여 주는 안내 팝업 (문의 메일 주소는 눌러서 복사)
Future<void> showBannedDialog(
  BuildContext context, {
  required String message,
  String contactEmail = '',
}) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: const Color(0xFF140028),
      title: const Row(
        children: [
          Icon(Icons.block, color: Colors.redAccent),
          SizedBox(width: 8),
          Text('이용이 정지된 계정이에요',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            contactEmail.isEmpty
                ? message
                : '궁금한 점이 있으면 아래 주소로 메일을 보내 주세요.\n정지 안내 메일에 답장해도 돼요.',
            style: const TextStyle(color: Colors.white70, height: 1.5),
          ),
          if (contactEmail.isNotEmpty) ...[
            const SizedBox(height: 14),
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () async {
                await Clipboard.setData(ClipboardData(text: contactEmail));
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx).showSnackBar(
                      const SnackBar(content: Text('메일 주소를 복사했어요.')));
                }
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A0B3A),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.mail_outline, color: Colors.purpleAccent, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SelectableText(contactEmail,
                          style: const TextStyle(color: Colors.white, fontSize: 15)),
                    ),
                    const Icon(Icons.copy, color: Colors.white38, size: 16),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('확인', style: TextStyle(color: Colors.purpleAccent)),
        ),
      ],
    ),
  );
}
