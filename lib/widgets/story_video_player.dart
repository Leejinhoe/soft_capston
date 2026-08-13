import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../main.dart';
import '../models/story_video.dart';

class StoryVideoPlayer extends StatefulWidget {
  final StoryVideoClip? clip;
  final String? videoUrl;
  final String title;
  final String description;
  final Map<String, String> httpHeaders;
  final bool autoplay;
  final bool loop;

  StoryVideoPlayer({
    super.key,
    required StoryVideoClip this.clip,
    this.autoplay = false,
    this.loop = false,
  }) : videoUrl = null,
       title = clip.title,
       description = clip.description,
       httpHeaders = const <String, String>{};

  const StoryVideoPlayer.network({
    super.key,
    required String this.videoUrl,
    this.title = '생성된 장면 영상',
    this.description = '이 장면의 이야기와 선택을 바탕으로 만든 영상입니다.',
    this.httpHeaders = const <String, String>{},
    this.autoplay = false,
    this.loop = false,
  }) : clip = null;

  String get source => clip == null ? videoUrl! : 'asset:///${clip!.assetPath}';

  String get sourceKey => clip?.id ?? videoUrl ?? '';

  @override
  State<StoryVideoPlayer> createState() => _StoryVideoPlayerState();
}

class _StoryVideoPlayerState extends State<StoryVideoPlayer>
    with WidgetsBindingObserver {
  static const int _maxWebVideoBytes = 64 * 1024 * 1024;

  late final Player _player;
  late final VideoController _controller;
  Media? _openedMedia;
  String? _error;
  int _loadRevision = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _player = Player();
    _controller = VideoController(_player);
    _openVideo();
  }

  @override
  void didUpdateWidget(covariant StoryVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sourceKey != widget.sourceKey ||
        oldWidget.autoplay != widget.autoplay ||
        oldWidget.loop != widget.loop) {
      _openVideo();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      unawaited(_player.pause());
    }
  }

  Future<void> _openVideo() async {
    final revision = ++_loadRevision;
    if (mounted) {
      setState(() {
        _error = null;
      });
    }
    try {
      await _player.setPlaylistMode(
        widget.loop ? PlaylistMode.single : PlaylistMode.none,
      );
      final media = await _loadMedia();
      if (!mounted || revision != _loadRevision) return;
      _openedMedia = media;
      await _player.open(media, play: widget.autoplay);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
      });
    }
  }

  Future<Media> _loadMedia() async {
    if (kIsWeb && widget.videoUrl != null) {
      final client = http.Client();
      try {
        final request = http.Request('GET', Uri.parse(widget.videoUrl!))
          ..headers.addAll(widget.httpHeaders);
        final response = await client
            .send(request)
            .timeout(const Duration(minutes: 2));
        if (response.statusCode != 200) {
          throw StateError('Video download failed: ${response.statusCode}');
        }
        if (response.contentLength != null &&
            response.contentLength! > _maxWebVideoBytes) {
          throw StateError('Video is too large to play safely in the browser.');
        }

        final bytes = BytesBuilder(copy: false);
        var received = 0;
        await for (final chunk in response.stream.timeout(
          const Duration(minutes: 2),
        )) {
          received += chunk.length;
          if (received > _maxWebVideoBytes) {
            throw StateError('Video is too large to play safely in the browser.');
          }
          bytes.add(chunk);
        }
        return Media.memory(
          bytes.takeBytes(),
          type: response.headers['content-type'] ?? 'video/mp4',
        );
      } finally {
        client.close();
      }
    }
    return Media(
      widget.source,
      httpHeaders: widget.httpHeaders.isEmpty ? null : widget.httpHeaders,
    );
  }

  void _replay() {
    unawaited(_player.seek(Duration.zero));
    unawaited(_player.play());
  }

  @override
  void dispose() {
    _loadRevision++;
    WidgetsBinding.instance.removeObserver(this);
    if (_openedMedia != null) {
      _openedMedia = null;
    }
    unawaited(_player.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.teal.withValues(alpha: 0.4)),
        boxShadow: [
          BoxShadow(
            color: AppColors.teal.withValues(alpha: 0.12),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 2,
            child: _error == null
                ? Video(controller: _controller)
                : Center(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Text(
                        '영상을 열 수 없습니다.',
                        style: TextStyle(color: AppColors.gray),
                      ),
                    ),
                  ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.auto_awesome_motion_rounded,
                  color: AppColors.teal,
                  size: 20,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.title,
                        style: const TextStyle(
                          color: AppColors.p300,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        widget.description,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppColors.gray,
                          fontSize: 11,
                          height: 1.35,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: '다시 재생',
                  onPressed: _error == null ? _replay : _openVideo,
                  icon: const Icon(Icons.replay_rounded),
                  color: AppColors.p300,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
