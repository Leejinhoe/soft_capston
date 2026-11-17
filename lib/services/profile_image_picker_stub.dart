import 'dart:typed_data';

class PickedProfileImage {
  final Uint8List bytes;
  final String filename;
  final String mimeType;

  const PickedProfileImage({
    required this.bytes,
    required this.filename,
    required this.mimeType,
  });
}

Future<PickedProfileImage?> pickProfileImage() async =>
    throw UnsupportedError('프로필 사진 선택은 Flutter Web에서 지원합니다.');
