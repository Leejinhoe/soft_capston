import 'package:flutter/material.dart';

import 'api_client.dart';

/// 동화 ↔ 커뮤니티 게시글 연결 처리 (수정/삭제 시 "함께 할까요?" 팝업)
///
/// - 게시글은 공유한 시점의 동화 복사본이고, 서버가 알려주는 `linked_id`로 서로 연결돼요.
///   (동화면 연결된 게시글 id, 게시글이면 원본 동화 id. 없으면 빈 문자열)
/// - 아니요를 골라도 연결은 그대로 유지돼요.
enum LinkedKind {
  story(
    path: '/api/stories',
    name: '동화',
    deleteQuestion: '커뮤니티 글도 지울까요?',
    deleteDetail: '커뮤니티에 올린 글도 함께 지울 수 있어요.',
    deleteBoth: '글도 함께 지우기',
    deleteOnly: '동화만 지우기',
    syncQuestion: '커뮤니티 글에도 반영할까요?',
    syncDetail: '커뮤니티에 올린 글도 같은 내용으로 바꿀 수 있어요.',
  ),
  post(
    path: '/api/posts',
    name: '게시글',
    deleteQuestion: '저장된 동화도 지울까요?',
    deleteDetail: '내 동화에 저장된 원본도 함께 지울 수 있어요.',
    deleteBoth: '동화도 함께 지우기',
    deleteOnly: '게시글만 지우기',
    syncQuestion: '내 동화에도 반영할까요?',
    syncDetail: '내 동화에 저장된 원본도 같은 내용으로 바꿀 수 있어요.',
  );

  const LinkedKind({
    required this.path,
    required this.name,
    required this.deleteQuestion,
    required this.deleteDetail,
    required this.deleteBoth,
    required this.deleteOnly,
    required this.syncQuestion,
    required this.syncDetail,
  });

  final String path;
  final String name;
  final String deleteQuestion;
  final String deleteDetail;
  final String deleteBoth;
  final String deleteOnly;
  final String syncQuestion;
  final String syncDetail;
}

const _card = Color(0xFF140028);

bool hasLink(Map<String, dynamic> item) =>
    (item['linked_id'] ?? '').toString().isNotEmpty;

ShapeBorder get _dialogShape => RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(20),
      side: const BorderSide(color: Colors.white10),
    );

const _titleStyle = TextStyle(color: Colors.white, fontWeight: FontWeight.bold);
const _bodyStyle = TextStyle(color: Colors.white70, height: 1.5);

void _toast(BuildContext context, String message) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
}

/// 삭제 확인 → (연결된 항목이 있으면 함께 지울지 묻기) → 서버 삭제.
/// 실제로 지웠으면 true.
Future<bool> deleteLinkedItem(
  BuildContext context,
  LinkedKind kind,
  Map<String, dynamic> item,
) async {
  final title = (item['title'] ?? '').toString();
  // null = 취소, false = 이것만, true = 함께
  final bool? withLinked = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      backgroundColor: _card,
      shape: _dialogShape,
      title: Text(hasLink(item) ? kind.deleteQuestion : '삭제할까요?', style: _titleStyle),
      content: Text(
        hasLink(item)
            ? '"$title" ${kind.name}을(를) 지워요.\n${kind.deleteDetail}'
            : '"$title"을(를) 지우면 되돌릴 수 없어요.',
        style: _bodyStyle,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('취소', style: TextStyle(color: Colors.white54)),
        ),
        if (hasLink(item))
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(kind.deleteOnly, style: const TextStyle(color: Colors.redAccent)),
          ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
          onPressed: () => Navigator.pop(context, hasLink(item)),
          child: Text(hasLink(item) ? kind.deleteBoth : '삭제',
              style: const TextStyle(color: Colors.white)),
        ),
      ],
    ),
  );
  if (withLinked == null || !context.mounted) return false;

  try {
    final response = await ApiClient.delete(
        '${kind.path}/${item['id']}${withLinked ? '?with_linked=true' : ''}');
    if (!context.mounted) return false;
    if (response.statusCode == 200) {
      _toast(context, withLinked ? '함께 지웠어요.' : '삭제했어요.');
      return true;
    }
    _toast(context, ApiClient.errorMessage(response));
  } catch (_) {
    if (context.mounted) _toast(context, '서버에 연결하지 못했어요.');
  }
  return false;
}

/// 수정 저장 전에 연결된 쪽에도 반영할지 묻습니다. null = 저장 취소.
Future<bool?> askSyncOnEdit(BuildContext context, LinkedKind kind) {
  return showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      backgroundColor: _card,
      shape: _dialogShape,
      title: Text(kind.syncQuestion, style: _titleStyle),
      content: Text(kind.syncDetail, style: _bodyStyle),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('아니요', style: TextStyle(color: Colors.white70)),
        ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF8B5CF6)),
          onPressed: () => Navigator.pop(context, true),
          child: const Text('네, 반영할게요', style: TextStyle(color: Colors.white)),
        ),
      ],
    ),
  );
}

/// 제목/내용 수정 화면. 저장에 성공하면 서버가 돌려준 항목을 pop 합니다.
class LinkedItemEditPage extends StatefulWidget {
  final LinkedKind kind;
  final Map<String, dynamic> item;

  const LinkedItemEditPage({super.key, required this.kind, required this.item});

  @override
  State<LinkedItemEditPage> createState() => _LinkedItemEditPageState();
}

class _LinkedItemEditPageState extends State<LinkedItemEditPage> {
  static const _bg = Color(0xFF070018);

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
      _toast(context, '제목과 내용을 모두 적어 주세요.');
      return;
    }

    var sync = false;
    if (hasLink(widget.item)) {
      final answer = await askSyncOnEdit(context, widget.kind);
      if (answer == null || !mounted) return;
      sync = answer;
    }

    setState(() => isSaving = true);
    try {
      final response = await ApiClient.patch(
        '${widget.kind.path}/${widget.item['id']}${sync ? '?sync=true' : ''}',
        body: {'title': title, 'content': content},
      );
      if (!mounted) return;
      if (response.statusCode == 200) {
        Navigator.pop(context, Map<String, dynamic>.from(ApiClient.decode(response)));
        return;
      }
      _toast(context, ApiClient.errorMessage(response));
    } catch (_) {
      if (mounted) _toast(context, '서버에 연결하지 못했어요.');
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
        title: Text('${widget.kind.name} 수정'),
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
