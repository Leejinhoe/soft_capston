import 'dart:async';
import 'dart:html' as html;
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

Future<PickedProfileImage?> pickProfileImage() async {
  final input = html.FileUploadInputElement()
    ..accept = 'image/png,image/jpeg,image/webp';
  input.click();
  await input.onChange.first.timeout(const Duration(minutes: 2));
  final files = input.files;
  if (files == null || files.isEmpty) return null;
  final file = files.first;
  if (file.size > 5 * 1024 * 1024) {
    throw Exception('사진은 5MB 이하로 선택해 주세요.');
  }
  final reader = html.FileReader()..readAsArrayBuffer(file);
  await Future.any([
    reader.onLoad.first,
    reader.onError.first.then((_) => throw Exception('사진 파일을 읽지 못했어요.')),
  ]);
  final result = reader.result;
  final Uint8List bytes;
  if (result is ByteBuffer) {
    bytes = result.asUint8List();
  } else if (result is Uint8List) {
    bytes = result;
  } else {
    throw Exception('사진 파일을 읽지 못했어요.');
  }
  return PickedProfileImage(
    bytes: bytes,
    filename: file.name,
    mimeType: file.type.isEmpty ? 'image/jpeg' : file.type,
  );
}
