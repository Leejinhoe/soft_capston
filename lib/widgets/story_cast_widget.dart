import 'package:flutter/material.dart';

import '../models/story_model.dart';

class StoryCastWidget extends StatelessWidget {
  final List<StoryCastMember> members;

  const StoryCastWidget({super.key, required this.members});

  static const _roleLabels = <String, String>{
    'hero': '주인공',
    'target': '구출 대상',
    'antagonist': '적대자',
    'companion': '동료',
    'guide': '조력자',
  };

  @override
  Widget build(BuildContext context) {
    if (members.isEmpty) return const SizedBox.shrink();

    final lockedCount = members
        .where((member) => member.characterKey.isNotEmpty)
        .length;
    final status = lockedCount == members.length
        ? '얼굴 고정 완료'
        : lockedCount > 0
        ? '$lockedCount/${members.length} 얼굴 고정'
        : '프로필 확인';

    return Align(
      alignment: Alignment.centerLeft,
      child: Tooltip(
        message: '동화 등장인물 배정 보기',
        child: TextButton.icon(
          key: const Key('story-cast-open'),
          onPressed: () => _showCastSheet(context),
          style: TextButton.styleFrom(
            foregroundColor: const Color(0xFFC4B5FD),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
              side: const BorderSide(color: Color(0x337C3AED)),
            ),
          ),
          icon: const Icon(Icons.people_outline_rounded, size: 17),
          label: Text(
            '등장인물 ${members.length}명 · $status',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }

  Future<void> _showCastSheet(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF0E0B28),
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.7,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(20, 0, 20, 12),
                child: Text(
                  '등장인물 배정',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Flexible(
                child: ListView.separated(
                  key: const Key('story-cast-list'),
                  shrinkWrap: true,
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 20),
                  itemCount: members.length,
                  separatorBuilder: (_, __) =>
                      const Divider(height: 1, color: Color(0x337C3AED)),
                  itemBuilder: (context, index) {
                    final member = members[index];
                    return ListTile(
                      dense: true,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      leading: CircleAvatar(
                        radius: 17,
                        backgroundColor: const Color(0x337C3AED),
                        child: Text(
                          _initialFor(member.name),
                          style: const TextStyle(
                            color: Color(0xFFC4B5FD),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      title: Text(
                        member.name.isEmpty ? '이름 미정' : member.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      subtitle: Text(
                        '${_roleLabel(member.role)} · ${member.identityLabel}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFF9CA3AF),
                          fontSize: 11,
                        ),
                      ),
                      trailing: member.characterKey.isEmpty
                          ? const Icon(
                              Icons.schedule_rounded,
                              size: 17,
                              color: Color(0xFF9CA3AF),
                            )
                          : const Icon(
                              Icons.lock_outline_rounded,
                              size: 17,
                              color: Color(0xFF14B8A6),
                            ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _roleLabel(String role) => _roleLabels[role] ?? role;

  static String _initialFor(String name) {
    final trimmed = name.trim();
    return trimmed.isEmpty ? '?' : trimmed.characters.first;
  }
}
