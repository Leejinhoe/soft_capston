import 'package:flutter/material.dart';

class CharacterStrip extends StatelessWidget {
  const CharacterStrip({super.key, required this.gender, required this.selectedKey,
    required this.onGenderChanged, required this.onSelected});

  final String gender;
  final String selectedKey;
  final ValueChanged<String> onGenderChanged;
  final ValueChanged<String> onSelected;

  static const names = {
    'male': ['민호', '준', '태산', '도윤', '보리', '레이븐', '이안', '하늘'],
    'female': ['미나', '하나', '미란', '루나', '서연', '아린', '나라', '솔'],
  };

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SegmentedButton<String>(
        segments: const [ButtonSegment(value: 'male', label: Text('남자')),
          ButtonSegment(value: 'female', label: Text('여자'))],
        selected: {gender},
        onSelectionChanged: (selection) => onGenderChanged(selection.first),
      ),
      SizedBox(height: 130, child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: 8,
        itemBuilder: (context, index) {
          final characterKey = '${gender}_0${index + 1}';
          return SizedBox(width: 88, child: InkWell(
            onTap: () => onSelected(characterKey),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Container(width: 68, height: 68,
                decoration: BoxDecoration(shape: BoxShape.circle,
                  border: Border.all(color: selectedKey == characterKey
                    ? Colors.amber : Colors.transparent, width: 3)),
                child: ClipOval(child: Transform.scale(scale: 2.1,
                  alignment: Alignment.topCenter,
                  child: Image.asset('assets/characters/${characterKey}_reference_v2.png',
                    fit: BoxFit.cover, alignment: Alignment.topCenter)))),
              const SizedBox(height: 6),
              Text(names[gender]![index], style: const TextStyle(color: Colors.white)),
            ]),
          ));
        },
      )),
    ]);
  }
}
