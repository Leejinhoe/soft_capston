/// 비밀번호 규칙 (회원가입·비밀번호 변경 공통, 서버 security.py와 같은 규칙)
/// 영문 소문자 / 대문자 / 숫자 / 특수문자 중 3가지 이상
/// 특수문자 = 영문·숫자·공백이 아닌 모든 문자 (~, _, -, 한글 등 포함)
const String kPasswordGuide = '영문 대/소문자, 숫자, 특수문자 중 3가지 이상 사용';

bool isStrongPassword(String password) {
  final rules = [
    RegExp(r'[a-z]'),
    RegExp(r'[A-Z]'),
    RegExp(r'[0-9]'),
    RegExp(r'[^A-Za-z0-9\s]'),
  ];
  return rules.where((rule) => rule.hasMatch(password)).length >= 3;
}
