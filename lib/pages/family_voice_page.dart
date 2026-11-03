import 'dart:async';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:record/record.dart';

import '../core/api_client.dart';

/// 마이페이지 > 우리 가족 목소리 (backend/voices.py)
/// - 목소리 최대 3개를 이름(엄마, 아빠, 나…)을 붙여 등록·삭제
/// - 등록: (1) 앱에서 바로 녹음 (record 패키지, 웹·안드로이드 둘 다) (2) 음성 파일 올리기
/// - 서버가 형식에 상관없이 XTTS용 WAV로 바꿔 저장 → 동화 화면 "동화 듣기"에서 이 목소리로 읽어 줌
class FamilyVoicePage extends StatefulWidget {
  const FamilyVoicePage({super.key});

  @override
  State<FamilyVoicePage> createState() => _FamilyVoicePageState();
}

const _bg = Color(0xFF070018);
const _card = Color(0xFF140028);
const _purple = Color(0xFF8B5CF6);
const _pink = Color(0xFFEC4899);

class _FamilyVoicePageState extends State<FamilyVoicePage> {
  bool loading = true;
  String? loadError;
  List<Map<String, dynamic>> voices = []; // 가족 목소리만 (기본 목소리 제외)
  int maxCount = 3;
  String sampleSentence = '';
  String notice = '녹음한 목소리는 동화 읽어주기에만 쓰이고, 언제든 지울 수 있어요.';
  String? deletingId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      loadError = null;
    });
    try {
      final response = await ApiClient.get('/api/voices');
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response) as Map;
        setState(() {
          voices = ((data['voices'] as List?) ?? [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .where((v) => v['is_default'] != true)
              .toList();
          maxCount = (data['max_count'] as num?)?.toInt() ?? 3;
          sampleSentence = (data['sample_sentence'] ?? '').toString();
          notice = (data['notice'] ?? notice).toString();
        });
      } else {
        setState(() => loadError = ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) setState(() => loadError = '서버에 연결하지 못했어요.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _openAdd() async {
    if (voices.length >= maxCount) {
      _toast('목소리는 $maxCount개까지 등록할 수 있어요. 하나를 지우고 다시 해 주세요.');
      return;
    }
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: _card,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (_) => _AddVoiceSheet(
        sampleSentence: sampleSentence,
        notice: notice,
        takenNames: voices.map((v) => (v['name'] ?? '').toString()).toSet(),
      ),
    );
    if (added == true) {
      _toast('목소리를 등록했어요! 동화 듣기에서 골라 보세요 🎙️');
      _load();
    }
  }

  Future<void> _delete(Map<String, dynamic> voice) async {
    final name = (voice['name'] ?? '').toString();
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _card,
        title: Text('"$name" 목소리를 지울까요?', style: const TextStyle(color: Colors.white)),
        content: const Text(
          '녹음한 목소리와, 이 목소리로 만든 동화 읽기 소리도 함께 지워져요.',
          style: TextStyle(color: Colors.white70, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('지우기', style: TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => deletingId = voice['id']?.toString());
    try {
      final response = await ApiClient.delete('/api/voices/${voice['id']}');
      if (response.statusCode == 200) {
        _toast('"$name" 목소리를 지웠어요.');
        await _load();
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      _toast('서버에 연결하지 못했어요.');
    } finally {
      if (mounted) setState(() => deletingId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: Colors.white,
        elevation: 0,
        title: const Text('우리 가족 목소리', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      floatingActionButton: loading || voices.length >= maxCount
          ? null
          : FloatingActionButton.extended(
              backgroundColor: _purple,
              onPressed: _openAdd,
              icon: const Icon(Icons.mic, color: Colors.white),
              label: const Text('목소리 등록',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
      body: loading
          ? const Center(child: CircularProgressIndicator(color: Colors.purpleAccent))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Text(
                    '엄마, 아빠 목소리로 동화를 들어요 🎧',
                    style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '목소리를 $maxCount개까지 등록할 수 있어요. 동화 화면의 "동화 듣기" 옆에서 누구 목소리로 들을지 고르면 돼요.',
                    style: const TextStyle(color: Colors.white60, fontSize: 14, height: 1.5),
                  ),
                  const SizedBox(height: 16),
                  _noticeBox(notice),
                  const SizedBox(height: 20),
                  if (loadError != null)
                    Text(loadError!, style: const TextStyle(color: Colors.redAccent))
                  else ...[
                    _voiceTile(const {'name': '기본 목소리(기계음)', 'is_default': true}),
                    for (final v in voices) _voiceTile(v),
                    if (voices.isEmpty)
                      const Padding(
                        padding: EdgeInsets.only(top: 8),
                        child: Text(
                          '아직 등록한 가족 목소리가 없어요. 아래 "목소리 등록"을 눌러 보세요!',
                          style: TextStyle(color: Colors.white54),
                        ),
                      ),
                  ],
                  const SizedBox(height: 100),
                ],
              ),
            ),
    );
  }

  Widget _voiceTile(Map<String, dynamic> v) {
    final isDefault = v['is_default'] == true;
    final duration = (v['duration_sec'] as num?)?.toDouble();
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: (isDefault ? Colors.white24 : _purple).withOpacity(0.35),
          child: Text(isDefault ? '🤖' : '🎙️'),
        ),
        title: Text((v['name'] ?? '').toString(),
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        subtitle: Text(
          isDefault
              ? '언제나 쓸 수 있는 기본 목소리예요'
              : '녹음 ${duration?.toStringAsFixed(1) ?? '-'}초',
          style: const TextStyle(color: Colors.white54, fontSize: 12),
        ),
        trailing: isDefault
            ? null
            : deletingId == v['id']
                ? const SizedBox(
                    width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                : IconButton(
                    tooltip: '지우기',
                    icon: const Icon(Icons.delete_outline, color: Colors.white54),
                    onPressed: () => _delete(v),
                  ),
      ),
    );
  }
}

Widget _noticeBox(String text) => Container(
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
          const Icon(Icons.lock_outline, color: Colors.white54, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                style: const TextStyle(color: Colors.white70, fontSize: 13, height: 1.5)),
          ),
        ],
      ),
    );

// ------------------------------------------------------------
// 목소리 등록 시트: 이름 + (녹음 | 파일 올리기)
// ------------------------------------------------------------
class _AddVoiceSheet extends StatefulWidget {
  final String sampleSentence;
  final String notice;
  final Set<String> takenNames;

  const _AddVoiceSheet({
    required this.sampleSentence,
    required this.notice,
    required this.takenNames,
  });

  @override
  State<_AddVoiceSheet> createState() => _AddVoiceSheetState();
}

/// 녹음 설정: PCM 16bit 모노 → 앱에서 WAV 머리말을 붙여 올림 (서버가 다시 XTTS용으로 변환)
const int _sampleRate = 44100;
const int _minSeconds = 3;
const int _goodSeconds = 5;
const int _maxSeconds = 15;

class _AddVoiceSheetState extends State<_AddVoiceSheet> {
  final TextEditingController nameController = TextEditingController();
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  StreamSubscription<Uint8List>? _sub;
  Timer? _timer;

  bool recording = false;
  bool uploading = false;
  int seconds = 0;
  final BytesBuilder _pcm = BytesBuilder(copy: false);

  // 올릴 준비가 된 소리 (녹음 또는 고른 파일)
  Uint8List? audioBytes;
  String audioName = '';
  String audioLabel = '';

  static const _presets = ['엄마', '아빠', '나', '할머니', '할아버지'];

  @override
  void dispose() {
    _timer?.cancel();
    _sub?.cancel();
    _recorder.dispose();
    _player.dispose();
    nameController.dispose();
    super.dispose();
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _startRecording() async {
    try {
      if (!await _recorder.hasPermission()) {
        _toast('마이크를 쓸 수 있게 허락해 주세요 🎤');
        return;
      }
      await _player.stop();
      _pcm.clear();
      final stream = await _recorder.startStream(const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: _sampleRate,
        numChannels: 1,
        echoCancel: true,
        noiseSuppress: true,
      ));
      _sub = stream.listen(_pcm.add);
      setState(() {
        recording = true;
        seconds = 0;
        audioBytes = null;
      });
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        setState(() => seconds++);
        if (seconds >= _maxSeconds) _stopRecording();
      });
    } catch (e) {
      debugPrint('녹음 시작 오류: $e');
      _toast('녹음을 시작하지 못했어요. 마이크를 확인해 주세요.');
    }
  }

  Future<void> _stopRecording() async {
    _timer?.cancel();
    _timer = null;
    try {
      await _recorder.stop();
    } catch (_) {}
    await _sub?.cancel();
    _sub = null;
    final pcm = _pcm.takeBytes();
    if (!mounted) return;
    setState(() => recording = false);
    final duration = pcm.length / (_sampleRate * 2);
    if (duration < _minSeconds) {
      _toast('$_minSeconds초보다 짧아요. 예시 문장을 끝까지 읽으며 다시 녹음해 주세요.');
      return;
    }
    setState(() {
      audioBytes = _wavFromPcm16(pcm, _sampleRate);
      audioName = 'recording.wav';
      audioLabel = '🎙️ 녹음 ${duration.toStringAsFixed(1)}초';
    });
  }

  Future<void> _pickFile() async {
    try {
      final file = await FilePicker.pickFile(type: FileType.audio);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      if (bytes.length > 20 * 1024 * 1024) {
        _toast('파일이 너무 커요. 20MB보다 작은 음성 파일을 골라 주세요.');
        return;
      }
      await _player.stop();
      setState(() {
        audioBytes = bytes;
        audioName = file.name;
        audioLabel = '📁 ${file.name}';
      });
    } catch (e) {
      debugPrint('파일 고르기 오류: $e');
      _toast('파일을 열지 못했어요.');
    }
  }

  Future<void> _preview() async {
    final bytes = audioBytes;
    if (bytes == null) return;
    try {
      final mime = audioName.endsWith('.wav') ? 'audio/wav' : 'audio/mpeg';
      await _player.setAudioSource(AudioSource.uri(Uri.dataFromBytes(bytes, mimeType: mime)));
      await _player.play();
    } catch (_) {
      _toast('미리 듣기를 할 수 없는 파일이에요. 그래도 올릴 수 있어요.');
    }
  }

  Future<void> _upload() async {
    final name = nameController.text.trim();
    final bytes = audioBytes;
    if (name.isEmpty) {
      _toast('누구 목소리인지 이름을 붙여 주세요. (예: 엄마)');
      return;
    }
    if (widget.takenNames.contains(name)) {
      _toast('"$name" 목소리가 벌써 있어요. 다른 이름을 붙여 주세요.');
      return;
    }
    if (bytes == null) {
      _toast('먼저 녹음하거나 음성 파일을 골라 주세요.');
      return;
    }
    setState(() => uploading = true);
    try {
      final response = await ApiClient.uploadFile(
        '/api/voices',
        field: 'file',
        bytes: bytes,
        filename: audioName,
        fields: {'name': name},
      );
      if (!mounted) return;
      if (response.statusCode == 200) {
        Navigator.pop(context, true);
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      _toast('서버에 연결하지 못했어요.');
    } finally {
      if (mounted) setState(() => uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(22, 18, 22, 22 + bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Center(
              child: Container(
                width: 44, height: 5,
                decoration: BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(3)),
              ),
            ),
            const SizedBox(height: 18),
            const Text('목소리 등록하기',
                style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            const Text('누구 목소리인가요?', style: TextStyle(color: Colors.white70)),
            const SizedBox(height: 8),
            TextField(
              controller: nameController,
              maxLength: 10,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: '예: 엄마',
                hintStyle: const TextStyle(color: Colors.white38),
                counterStyle: const TextStyle(color: Colors.white38),
                filled: true,
                fillColor: const Color(0xFF1A0B3A),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
              ),
            ),
            Wrap(
              spacing: 8,
              children: _presets
                  .where((p) => !widget.takenNames.contains(p))
                  .map((p) => ActionChip(
                        label: Text(p),
                        backgroundColor: const Color(0xFF1A0B3A),
                        labelStyle: const TextStyle(color: Colors.white),
                        onPressed: () => setState(() => nameController.text = p),
                      ))
                  .toList(),
            ),
            const SizedBox(height: 20),
            // 따라 읽을 예시 문장
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [_purple.withOpacity(0.25), _pink.withOpacity(0.2)]),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('📖 이 문장을 또박또박 읽어 주세요 (5~10초)',
                      style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text(widget.sampleSentence,
                      style: const TextStyle(color: Colors.white, fontSize: 17, height: 1.6)),
                  const SizedBox(height: 8),
                  const Text('조용한 곳에서, 동화를 읽어 주듯 편안하게 말하면 가장 잘 돼요.',
                      style: TextStyle(color: Colors.white54, fontSize: 12)),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: recording ? Colors.redAccent : _purple,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    onPressed: uploading ? null : (recording ? _stopRecording : _startRecording),
                    icon: Icon(recording ? Icons.stop_circle : Icons.mic, color: Colors.white),
                    label: Text(
                      recording ? '그만 녹음하기 ($seconds초)' : '바로 녹음하기',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white24),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    onPressed: (uploading || recording) ? null : _pickFile,
                    icon: const Icon(Icons.upload_file),
                    label: const Text('음성 파일 올리기'),
                  ),
                ),
              ],
            ),
            if (recording) ...[
              const SizedBox(height: 10),
              LinearProgressIndicator(
                value: (seconds / _maxSeconds).clamp(0, 1).toDouble(),
                color: seconds >= _goodSeconds ? Colors.greenAccent : Colors.amber,
                backgroundColor: Colors.white12,
              ),
              const SizedBox(height: 6),
              Text(
                seconds < _goodSeconds ? '조금 더 읽어 주세요… ($_goodSeconds초 이상이면 좋아요)' : '좋아요! 다 읽었으면 "그만 녹음하기"를 눌러요',
                style: const TextStyle(color: Colors.white60, fontSize: 12),
              ),
            ],
            if (audioBytes != null) ...[
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: Text(audioLabel,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  ),
                  TextButton.icon(
                    onPressed: _preview,
                    icon: const Icon(Icons.play_arrow, color: Colors.purpleAccent),
                    label: const Text('들어 보기', style: TextStyle(color: Colors.purpleAccent)),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 14),
            _noticeBox(widget.notice),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: _pink,
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                ),
                onPressed: (uploading || recording || audioBytes == null) ? null : _upload,
                child: uploading
                    ? const SizedBox(
                        width: 22, height: 22,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5))
                    : const Text('이 목소리 등록하기',
                        style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// PCM 16bit 리틀엔디언 모노 → WAV 파일 바이트
Uint8List _wavFromPcm16(Uint8List pcm, int sampleRate) {
  const channels = 1;
  const bitsPerSample = 16;
  final byteRate = sampleRate * channels * bitsPerSample ~/ 8;
  final header = ByteData(44);
  void ascii(int offset, String s) {
    for (var i = 0; i < s.length; i++) {
      header.setUint8(offset + i, s.codeUnitAt(i));
    }
  }

  ascii(0, 'RIFF');
  header.setUint32(4, 36 + pcm.length, Endian.little);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  header.setUint32(16, 16, Endian.little);
  header.setUint16(20, 1, Endian.little); // PCM
  header.setUint16(22, channels, Endian.little);
  header.setUint32(24, sampleRate, Endian.little);
  header.setUint32(28, byteRate, Endian.little);
  header.setUint16(32, channels * bitsPerSample ~/ 8, Endian.little);
  header.setUint16(34, bitsPerSample, Endian.little);
  ascii(36, 'data');
  header.setUint32(40, pcm.length, Endian.little);
  final out = BytesBuilder(copy: false)
    ..add(header.buffer.asUint8List())
    ..add(pcm);
  return out.takeBytes();
}
