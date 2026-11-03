import 'package:flutter/material.dart';

/// 심리분석 성향 5가지 (순서·key는 backend/psych_engine.py의 TRAITS와 같게)
/// 색은 어두운 배경에서 서로 잘 구분되는 고정 순서 팔레트 (성향마다 항상 같은 색)
class PsychTrait {
  final String key;
  final String label;
  final String shortLabel;
  final String emoji;
  final Color color;

  const PsychTrait(this.key, this.label, this.shortLabel, this.emoji, this.color);

  /// "용기·도전이", "호기심·탐구가" (받침에 맞는 조사)
  String get labelWithSubject {
    final last = label.codeUnitAt(label.length - 1);
    final hasJong = last >= 0xAC00 && last <= 0xD7A3 && (last - 0xAC00) % 28 != 0;
    return '$label${hasJong ? '이' : '가'}';
  }
}

const List<PsychTrait> kPsychTraits = [
  PsychTrait('courage', '용기·도전', '용기', '🦁', Color(0xFF3987E5)),
  PsychTrait('empathy', '배려·공감', '배려', '🤝', Color(0xFFD95926)),
  PsychTrait('curiosity', '호기심·탐구', '호기심', '🔍', Color(0xFF199E70)),
  PsychTrait('caution', '신중함', '신중', '🐢', Color(0xFFC98500)),
  PsychTrait('creativity', '창의성', '창의', '🎨', Color(0xFFD55181)),
];

PsychTrait psychTraitOf(String? key) =>
    kPsychTraits.firstWhere((t) => t.key == key, orElse: () => kPsychTraits.first);

/// {key: 점수} → 성향 순서대로 0~100 숫자
double traitScore(Map? traits, String key) {
  final value = traits?[key];
  if (value is num) return value.toDouble().clamp(0, 100).toDouble();
  return 0;
}

/// 서버 시간(UTC, 시간대 표시 없음) → "11월 4일"
String psychDateLabel(dynamic raw) {
  if (raw is! String || raw.isEmpty) return '';
  final text = raw.endsWith('Z') || raw.contains('+') ? raw : '${raw}Z';
  final date = DateTime.tryParse(text)?.toLocal();
  if (date == null) return '';
  return '${date.month}월 ${date.day}일';
}

/// 심리 화면 공통 색
const Color kMindBg = Color(0xFF070018);
const Color kMindCard = Color(0xFF140028);
const Color kMindPurple = Color(0xFF8B5CF6);
const Color kMindPink = Color(0xFFEC4899);

/// "진단이 아니에요" 안내 상자
class PsychNotice extends StatelessWidget {
  final String text;

  const PsychNotice({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, color: Colors.white54, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Colors.white60, fontSize: 13, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}

/// 카드 틀
class MindCard extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget child;

  const MindCard({super.key, required this.title, this.subtitle, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: kMindCard,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
          if (subtitle != null) ...[
            const SizedBox(height: 6),
            Text(subtitle!, style: const TextStyle(color: Colors.white60, fontSize: 14, height: 1.4)),
          ],
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}
