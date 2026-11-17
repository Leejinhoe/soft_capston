import 'package:fairytale_hyeonlim_merged/utils/korean_word_normalizer.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('strips Korean case and topic particles from clicked words', () {
    expect(KoreanWordNormalizer.lookupWord('사과를'), '사과');
    expect(KoreanWordNormalizer.lookupWord('숲에서는'), '숲');
    expect(KoreanWordNormalizer.lookupWord('친구에게는'), '친구');
    expect(KoreanWordNormalizer.lookupWord('길로'), '길');
    expect(KoreanWordNormalizer.lookupWord('책은'), '책');
  });

  test(
    'preserves common lexical words that end in particle-like syllables',
    () {
      expect(KoreanWordNormalizer.lookupWord('아이'), '아이');
      expect(KoreanWordNormalizer.lookupWord('종이'), '종이');
      expect(KoreanWordNormalizer.lookupWord('고양이'), '고양이');
      expect(KoreanWordNormalizer.lookupWord('사과'), '사과');
      expect(KoreanWordNormalizer.lookupWord('지도'), '지도');
      expect(KoreanWordNormalizer.lookupWord('작은'), '작은');
    },
  );
}
