import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../core/api_client.dart';

class SceneVideo extends StatefulWidget {
  const SceneVideo({super.key, required this.storyId, required this.sceneNumber, this.journey = false});

  final String storyId;
  final int sceneNumber;
  final bool journey;

  @override
  State<SceneVideo> createState() => _SceneVideoState();
}

class _SceneVideoState extends State<SceneVideo> {
  late final Player _player;
  late final VideoController _controller;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _player = Player();
    _controller = VideoController(_player);
    _load();
  }

  Future<void> _load() async {
    try {
      final path = widget.journey
          ? '/api/stories/${widget.storyId}/journey-video'
          : '/api/stories/${widget.storyId}/scenes/${widget.sceneNumber}/video';
      final response = await ApiClient.get(path);
      if (response.statusCode != 200 || response.bodyBytes.isEmpty ||
          response.bodyBytes.length > 30000000) {
        throw StateError('Video unavailable');
      }
      final media = await Media.memory(response.bodyBytes, type: 'video/mp4');
      if (!mounted) return;
      await _player.open(media, play: false);
    } catch (_) {
      if (mounted) _error = '장면 영상을 불러오지 못했어요.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Text(_error!, style: const TextStyle(color: Colors.white70));
    return AspectRatio(aspectRatio: 16 / 9, child: Video(controller: _controller));
  }
}
