/// Removes common Korean case/topic particles from a clicked story token.
///
/// This is intentionally conservative: common lexical words that happen to end
/// in a particle-shaped syllable are preserved.
class KoreanWordNormalizer {
  KoreanWordNormalizer._();

  static const _particles = <String>[
    '에게에서는',
    '에게서도',
    '에게서는',
    '한테에서는',
    '한테서도',
    '한테서는',
    '으로부터',
    '에서부터',
    '에게까지',
    '한테까지',
    '으로서는',
    '으로써는',
    '에게는',
    '에게도',
    '에게만',
    '에게랑',
    '한테는',
    '한테도',
    '한테만',
    '께서는',
    '께서도',
    '으로는',
    '으로도',
    '으로만',
    '으로',
    '에서는',
    '에서도',
    '에서만',
    '에게서',
    '한테서',
    '께서',
    '이랑',
    '까지',
    '부터',
    '처럼',
    '보다',
    '한테',
    '에게',
    '으로서',
    '으로써',
    '은',
    '는',
    '이',
    '가',
    '을',
    '를',
    '과',
    '와',
    '로',
    '도',
    '만',
    '의',
    '에',
    '랑',
  ];

  static const _lexicalExceptions = <String>{
    '아이',
    '고양이',
    '거북이',
    '원숭이',
    '호랑이',
    '반딧불이',
    '길이',
    '종이',
    '먹이',
    '놀이',
    '오이',
    '나이',
    '회의',
    '풀이',
    '송이',
    '깊이',
    '높이',
    '많이',
    '없이',
    '같이',
    '화가',
    '작가',
    '국가',
    '작은',
    '좋은',
    '많은',
    '높은',
    '넓은',
    '젊은',
    '맑은',
    '굵은',
    '밝은',
    '깊은',
    '좁은',
    '낮은',
    '짧은',
    '옳은',
    '낡은',
    '가는',
    '나는',
    '보는',
    '하는',
    '있는',
    '없는',
    '웃는',
    '큰',
    '긴',
    '먼',
  };
  static const _singleSyllableWords = <String>{
    '길',
    '책',
    '집',
    '숲',
    '꽃',
    '별',
    '달',
    '밤',
    '꿈',
    '물',
    '불',
    '산',
    '강',
    '문',
    '손',
    '눈',
    '말',
    '빛',
    '힘',
    '밥',
    '돌',
    '풀',
    '잎',
    '방',
    '곰',
    '용',
    '왕',
    '공',
    '밭',
    '쌀',
    '떡',
    '새',
    '해',
    '배',
    '개',
    '발',
    '땅',
  };

  static String lookupWord(String surface) {
    var word = surface.replaceAll(RegExp(r'[^가-힣]'), '').trim();
    if (word.length < 2 || _lexicalExceptions.contains(word)) return word;

    // Multi-particle forms such as "친구에게는" are listed as one suffix.
    // Stripping once avoids mistaking the end of the remaining noun (사과의 "과")
    // for a second particle.
    final particle = _particles.firstWhere(
      (suffix) => word.endsWith(suffix) && word.length > suffix.length,
      orElse: () => '',
    );
    if (particle.isEmpty) return word;
    final stem = word.substring(0, word.length - particle.length);
    if (stem.isEmpty || !_canAttachParticle(stem, particle)) return word;
    if (stem.length == 1 && !_singleSyllableWords.contains(stem)) return word;
    return stem;
  }

  static bool _canAttachParticle(String stem, String particle) {
    final last = stem.codeUnitAt(stem.length - 1);
    if (last < 0xAC00 || last > 0xD7A3) return true;
    final jong = (last - 0xAC00) % 28;
    switch (particle) {
      case '이':
      case '은':
      case '을':
        return jong != 0;
      case '가':
      case '는':
      case '를':
        return jong == 0;
      case '으로':
        return jong != 0 && jong != 8; // ㄹ 받침은 "로"
      case '로':
        return jong == 0 || jong == 8;
      default:
        return true;
    }
  }
}
