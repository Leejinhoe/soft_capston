import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class StoryCharacterAnimation extends StatefulWidget {
  final String characterKey;
  final String storyText;
  final String genre;

  const StoryCharacterAnimation({
    super.key,
    required this.characterKey,
    required this.storyText,
    required this.genre,
  });

  static final RegExp _catalogCharacterPattern = RegExp(
    r'^(male|female)_0[1-8]$',
  );

  static const String motionAssetVersion = 'v28';
  static const String legacyMotionAssetVersion = 'v23';

  static const List<String> _movementTerms = <String>[
    'run',
    'running',
    'rush',
    'walk',
    'walking',
    'toward',
    'move',
    'travel',
    '\ub2ec\ub9ac',
    '\ub6f0',
    '\uac77',
    '\ud5a5\ud574',
    '\ub098\uc544\uac00',
    '\uc774\ub3d9',
    '\ub5a0\ub098',
  ];

  static const List<String> _actionTerms = <String>[
    ..._movementTerms,
    'jump',
    'leap',
    'hop',
    'battle',
    'fight',
    'attack',
    'strike',
    'slash',
    'sword',
    'interact',
    'reach',
    'receive',
    'give',
    'hand',
    'rescue',
    'help',
    'wave',
    'greet',
    'magic',
    'spell',
    'investigate',
    'search',
    '\uc810\ud504',
    '\ub3c4\uc57d',
    '\uc2f8\uc6b0',
    '\uacf5\uaca9',
    '\uc804\ud22c',
    '\uce7c',
    '\ubca0',
    '\uac74\ub124',
    '\ubc1b',
    '\uc7a1',
    '\uad6c\ud574',
    '\ub3d5',
    '\uc5f4',
    '\uc778\uc0ac',
    '\ub9c8\ubc95',
    '\uc8fc\ubb38',
    '\uc0b4\ud3b4',
    '\uc870\uc0ac',
    '\ucc3e',
  ];

  static bool supports({
    required String characterKey,
    required String storyText,
  }) {
    final normalizedKey = characterKey.trim().toLowerCase();
    if (!_catalogCharacterPattern.hasMatch(normalizedKey)) return false;
    final normalizedStory = storyText.toLowerCase();
    return _actionTerms.any(normalizedStory.contains);
  }

  static String _animationActionFor(String storyText) {
    final story = storyText.toLowerCase();
    const jumpTerms = <String>[
      'jump', 'leap', 'hop', '\uc810\ud504', '\ub3c4\uc57d', '\ub6f0\uc5b4\uc624',
    ];
    const battleTerms = <String>[
      'battle', 'fight', 'attack', 'strike', 'slash', 'sword',
      '\uc2f8\uc6b0', '\uacf5\uaca9', '\uc804\ud22c', '\uce7c', '\ubca0',
    ];
    const interactionTerms = <String>[
      'interact', 'reach', 'receive', 'give', 'hand', 'rescue', 'help',
      '\uac74\ub124', '\ubc1b', '\uc7a1', '\uad6c\ud574', '\ub3d5', '\uc5f4',
    ];
    const actionSheetTerms = <String>[
      'wave', 'greet', 'magic', 'spell', 'investigate', 'search',
      '\uc778\uc0ac', '\ub9c8\ubc95', '\uc8fc\ubb38', '\uc0b4\ud3b4', '\uc870\uc0ac', '\ucc3e',
    ];
    if (jumpTerms.any(story.contains)) return 'jump';
    if (battleTerms.any(story.contains)) return 'battle';
    if (interactionTerms.any(story.contains)) return 'interaction';
    if (actionSheetTerms.any(story.contains)) return 'action';
    if (_movementTerms.any(story.contains)) return 'run';
    return 'run';
  }

  static String animationActionFor(String storyText) =>
      _animationActionFor(storyText);

  static bool usesMovingBackgroundForStory(String storyText) =>
      _animationActionFor(storyText) == 'run';

  static String motionSheetAssetPath({
    required String characterKey,
    required String action,
    String version = motionAssetVersion,
  }) {
    final normalizedKey = characterKey.trim().toLowerCase();
    final filename = switch (action) {
      'jump' => 'jump_cycle',
      'battle' => 'battle_cycle',
      'interaction' => 'interaction_cycle',
      'action' => 'action_sheet',
      _ => throw ArgumentError.value(action, 'action'),
    };
    return 'assets/characters/motion_sheets/'
        '${normalizedKey}_${filename}_$version.png';
  }

  @override
  State<StoryCharacterAnimation> createState() =>
      _StoryCharacterAnimationState();
}

class _StoryCharacterAnimationState extends State<StoryCharacterAnimation>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  ui.Image? _backgroundImage;
  ui.Image? _spriteSheetImage;
  Object? _loadError;
  bool _paused = false;
  int _loadRevision = 0;

  String get _normalizedCharacterKey =>
      widget.characterKey.trim().toLowerCase();

  String get _animationAction =>
      StoryCharacterAnimation._animationActionFor(widget.storyText);

  bool get _usesHighQualityRunCycle =>
      StoryCharacterAnimation._catalogCharacterPattern
          .hasMatch(_normalizedCharacterKey);

  bool get _isRunning {
    return _animationAction == 'run';
  }

  int get _sheetRows => 2;

  String get _spriteSheetAsset {
    if (_isDedicatedAction) {
      return StoryCharacterAnimation.motionSheetAssetPath(
        characterKey: _normalizedCharacterKey,
        action: _animationAction,
      );
    }
    final prefix = 'assets/characters/motion_sheets/$_normalizedCharacterKey';
    return _usesHighQualityRunCycle
        ? '${prefix}_run_cycle_v16.png'
        : '${prefix}_target_journey_sheet_v4.png';
  }

  List<String> get _spriteSheetAssetCandidates {
    if (!_isDedicatedAction) return <String>[_spriteSheetAsset];
    return <String>[
      _spriteSheetAsset,
      StoryCharacterAnimation.motionSheetAssetPath(
        characterKey: _normalizedCharacterKey,
        action: _animationAction,
        version: StoryCharacterAnimation.legacyMotionAssetVersion,
      ),
    ];
  }

  bool get _isDedicatedAction =>
      const <String>{'jump', 'battle', 'interaction', 'action'}
          .contains(_animationAction);

  Duration get _animationDuration {
    switch (_animationAction) {
      case 'jump':
        return const Duration(seconds: 4);
      case 'battle':
      case 'interaction':
        return const Duration(seconds: 6);
      case 'action':
        return const Duration(seconds: 7);
      default:
        return Duration(seconds: _isRunning ? 8 : 11);
    }
  }

  String get _backgroundAsset {
    final story = widget.storyText.toLowerCase();
    if (story.contains('castle') || story.contains('\uc131')) {
      return 'assets/backgrounds/fantasy_castle_wide_v2.png';
    }
    switch (widget.genre.trim().toLowerCase()) {
      case 'adventure':
        return 'assets/backgrounds/adventure_ruins_wide_v2.png';
      case 'nature':
        return 'assets/backgrounds/nature_pond_wide_v2.png';
      case 'friendship':
        return 'assets/backgrounds/friendship_square_wide_v2.png';
      case 'mystery':
        return 'assets/backgrounds/mystery_library_wide_v2.png';
      default:
        return 'assets/backgrounds/fantasy_castle_wide_v2.png';
    }
  }

  String get _routeKey {
    final asset = _backgroundAsset;
    if (asset.contains('adventure_')) return 'adventure';
    if (asset.contains('nature_')) return 'nature';
    if (asset.contains('friendship_')) return 'friendship';
    if (asset.contains('mystery_')) return 'mystery';
    return 'castle';
  }

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: _animationDuration);
    _controller.addStatusListener(_handleAnimationStatus);
    _controller.forward();
    _loadImages();
  }

  void _handleAnimationStatus(AnimationStatus status) {
    if (status == AnimationStatus.completed && mounted && !_paused) {
      setState(() {
        _paused = true;
      });
    }
  }

  @override
  void didUpdateWidget(covariant StoryCharacterAnimation oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.characterKey != widget.characterKey ||
        oldWidget.genre != widget.genre ||
        oldWidget.storyText != widget.storyText) {
      _paused = false;
      _controller.duration = _animationDuration;
      _controller.forward(from: 0);
      _loadImages();
    }
  }

  Future<ui.Image> _loadImage(String assetPath) async {
    final data = await rootBundle.load(assetPath);
    final codec = await ui.instantiateImageCodec(
      data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
    );
    final frame = await codec.getNextFrame();
    codec.dispose();
    return frame.image;
  }

  Future<ui.Image> _loadFirstAvailableImage(List<String> assetPaths) async {
    Object? lastError;
    for (final assetPath in assetPaths) {
      try {
        return await _loadImage(assetPath);
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError ?? StateError('No motion asset candidates were provided.');
  }

  Future<void> _loadImages() async {
    final revision = ++_loadRevision;
    setState(() {
      _loadError = null;
    });
    try {
      final images = await Future.wait<ui.Image>([
        _loadImage(_backgroundAsset),
        _loadFirstAvailableImage(_spriteSheetAssetCandidates),
      ]);
      if (!mounted || revision != _loadRevision) {
        for (final image in images) {
          image.dispose();
        }
        return;
      }
      final previousBackground = _backgroundImage;
      final previousSprite = _spriteSheetImage;
      setState(() {
        _backgroundImage = images[0];
        _spriteSheetImage = images[1];
      });
      previousBackground?.dispose();
      previousSprite?.dispose();
    } catch (error) {
      if (!mounted || revision != _loadRevision) return;
      setState(() {
        _loadError = error;
      });
    }
  }

  void _togglePlayback() {
    setState(() {
      _paused = !_paused;
      if (_paused) {
        _controller.stop();
      } else {
        if (_controller.isCompleted) {
          _controller.forward(from: 0);
        } else {
          _controller.forward();
        }
      }
    });
  }

  @override
  void dispose() {
    _loadRevision++;
    _controller.dispose();
    _backgroundImage?.dispose();
    _spriteSheetImage?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ready = _backgroundImage != null && _spriteSheetImage != null;
    return AspectRatio(
      aspectRatio: 2,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: ColoredBox(
          color: const Color(0xff15192b),
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (ready)
                AnimatedBuilder(
                  animation: _controller,
                  builder: (context, child) => CustomPaint(
                    key: const Key('story-character-animation-movement'),
                    painter: _StoryCharacterMovementPainter(
                      backgroundImage: _backgroundImage!,
                      spriteSheetImage: _spriteSheetImage!,
                      progress: _controller.value,
                      rows: _sheetRows,
                      identityLockedMotion: _usesHighQualityRunCycle,
                      action: _animationAction,
                      running: _isRunning,
                      routeKey: _routeKey,
                    ),
                  ),
                )
              else if (_loadError != null)
                Center(
                  child: Image.asset(
                    'assets/characters/'
                    '${_normalizedCharacterKey}_reference_v2.png',
                    fit: BoxFit.contain,
                    errorBuilder: (context, error, stackTrace) => const Icon(
                      Icons.image_not_supported_outlined,
                      color: Colors.white70,
                    ),
                  ),
                )
              else
                const Center(
                  child: SizedBox.square(
                    dimension: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              Positioned(
                right: 8,
                top: 8,
                child: Tooltip(
                  message:
                      _paused ? '\uc7ac\uc0dd' : '\uc77c\uc2dc\uc815\uc9c0',
                  child: IconButton.filledTonal(
                    key: const Key('story-character-animation-toggle'),
                    onPressed: _togglePlayback,
                    icon: Icon(_paused ? Icons.play_arrow : Icons.pause),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StoryCharacterMovementPainter extends CustomPainter {
  final ui.Image backgroundImage;
  final ui.Image spriteSheetImage;
  final double progress;
  final int rows;
  final bool identityLockedMotion;
  final String action;
  final bool running;
  final String routeKey;

  const _StoryCharacterMovementPainter({
    required this.backgroundImage,
    required this.spriteSheetImage,
    required this.progress,
    required this.rows,
    required this.identityLockedMotion,
    required this.action,
    required this.running,
    required this.routeKey,
  });

  static const int _columns = 4;
  static const List<int> _runFrameSequence = <int>[0, 1, 2, 3, 4, 5, 6, 7];
  static const List<int> _walkFrameSequence = <int>[0, 1, 4, 5, 6, 5, 4, 1];
  static const List<int> _actionFrameSequence = <int>[0, 1, 2, 3, 4, 5, 6, 7];
  static const Rect _normalizedRunVisibleBounds = Rect.fromLTWH(
    5 / 384,
    60 / 512,
    374 / 384,
    420 / 512,
  );
  static const List<Offset> _castleRoad = <Offset>[
    Offset(0.53, 0.96),
    Offset(0.60, 0.88),
    Offset(0.67, 0.79),
    Offset(0.72, 0.69),
    Offset(0.78, 0.58),
    Offset(0.86, 0.43),
  ];
  static const Map<String, List<Offset>> _routes = <String, List<Offset>>{
    'castle': _castleRoad,
    'adventure': <Offset>[
      Offset(0.13, 0.88),
      Offset(0.28, 0.84),
      Offset(0.45, 0.80),
      Offset(0.63, 0.75),
      Offset(0.84, 0.68),
    ],
    'nature': <Offset>[
      Offset(0.12, 0.84),
      Offset(0.29, 0.82),
      Offset(0.47, 0.80),
      Offset(0.66, 0.79),
      Offset(0.86, 0.76),
    ],
    'friendship': <Offset>[
      Offset(0.14, 0.87),
      Offset(0.31, 0.86),
      Offset(0.50, 0.85),
      Offset(0.69, 0.84),
      Offset(0.86, 0.83),
    ],
    'mystery': <Offset>[
      Offset(0.15, 0.90),
      Offset(0.30, 0.84),
      Offset(0.46, 0.77),
      Offset(0.62, 0.68),
      Offset(0.78, 0.58),
    ],
  };

  @override
  void paint(Canvas canvas, Size size) {
    _paintCoverImage(canvas, size, backgroundImage);

    final cellCount = _columns * rows;
    final cycleCount = action == 'run'
        ? (running ? 6.0 : 3.4)
        : action == 'jump'
            ? 1.15
            : action == 'battle'
                ? 1.45
                : action == 'interaction'
                    ? 1.25
                    : 1.6;
    final sequence = identityLockedMotion
        ? (action == 'run'
            ? (running ? _runFrameSequence : _walkFrameSequence)
            : _actionFrameSequence)
        : List<int>.generate(cellCount, (index) => index);
    final framePosition = progress * cycleCount * sequence.length;
    final sequencePosition = framePosition.floor();
    final frameIndex = sequence[sequencePosition % sequence.length];
    final nextFrameIndex = sequence[(sequencePosition + 1) % sequence.length];
    final blend = identityLockedMotion && action != 'jump'
        ? framePosition - sequencePosition
        : 0.0;
    final cellWidth = spriteSheetImage.width / _columns;
    final cellHeight = spriteSheetImage.height / rows;
    final source = _sourceRect(frameIndex, cellWidth, cellHeight);
    final nextSource = _sourceRect(nextFrameIndex, cellWidth, cellHeight);
    final visibleBounds = _visibleBounds(frameIndex);
    final nextVisibleBounds = _visibleBounds(nextFrameIndex);

    final hasStrongPerspective = routeKey == 'castle' || routeKey == 'mystery';
    final isLocomotion = action == 'run';
    final targetHeight = size.height *
        (isLocomotion
            ? (hasStrongPerspective
                ? (0.48 - 0.18 * progress)
                : (0.42 - 0.06 * progress))
            : 0.56);
    final routePosition = _sampleRoute(isLocomotion ? progress : 0.52);
    final centerX = size.width * routePosition.dx;
    final groundY = size.height * routePosition.dy;
    final runPhase = (progress * cycleCount) % 1.0;
    final groundContact = action == 'jump'
        ? (frameIndex == 0 || frameIndex >= 5 ? 1.0 : 0.28)
        : action == 'run' && identityLockedMotion
            ? 0.5 + 0.5 * math.cos(runPhase * math.pi * 4.0)
            : 1.0;
    final destination = _destinationRect(
      source: source,
      visibleBounds: visibleBounds,
      centerX: centerX,
      groundY: groundY,
      targetHeight: targetHeight,
    );
    final nextDestination = _destinationRect(
      source: nextSource,
      visibleBounds: nextVisibleBounds,
      centerX: centerX,
      groundY: groundY,
      targetHeight: targetHeight,
    );
    final shadowWidth =
        destination.width * visibleBounds.width * (1.0 - blend) +
            nextDestination.width * nextVisibleBounds.width * blend;

    final shadowPaint = Paint()
      ..color = Colors.black.withValues(
        alpha: 0.14 + groundContact * 0.10,
      )
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(centerX, groundY),
        width: shadowWidth * (0.35 + groundContact * 0.12),
        height: targetHeight * (0.045 + groundContact * 0.015),
      ),
      shadowPaint,
    );
    canvas.drawImageRect(
      spriteSheetImage,
      source,
      destination,
      Paint()
        ..filterQuality = FilterQuality.high
        ..color = Colors.white.withValues(alpha: 1.0 - blend),
    );
    if (blend > 0.0) {
      canvas.drawImageRect(
        spriteSheetImage,
        nextSource,
        nextDestination,
        Paint()
          ..filterQuality = FilterQuality.high
          ..color = Colors.white.withValues(alpha: blend),
      );
    }
  }

  Rect _sourceRect(int frameIndex, double cellWidth, double cellHeight) {
    final column = frameIndex % _columns;
    final row = frameIndex ~/ _columns;
    return Rect.fromLTWH(
      column * cellWidth,
      row * cellHeight,
      cellWidth,
      cellHeight,
    );
  }

  Rect _visibleBounds(int frameIndex) {
    return identityLockedMotion
        ? _normalizedRunVisibleBounds
        : const Rect.fromLTWH(0, 0, 1, 1);
  }

  Rect _destinationRect({
    required Rect source,
    required Rect visibleBounds,
    required double centerX,
    required double groundY,
    required double targetHeight,
  }) {
    const referenceVisibleHeight = 420 / 512;
    final canvasHeight = identityLockedMotion
        ? targetHeight / referenceVisibleHeight
        : targetHeight;
    final canvasWidth = canvasHeight * source.width / source.height;
    return Rect.fromLTWH(
      centerX - visibleBounds.center.dx * canvasWidth,
      groundY - visibleBounds.bottom * canvasHeight,
      canvasWidth,
      canvasHeight,
    );
  }

  Offset _sampleRoute(double value) {
    final route = _routes[routeKey] ?? _castleRoad;
    final normalized = value.clamp(0.0, 1.0);
    final position = normalized * (route.length - 1);
    final index = position.floor().clamp(0, route.length - 2);
    final local = position - index;
    final p0 = route[math.max(index - 1, 0)];
    final p1 = route[index];
    final p2 = route[index + 1];
    final p3 = route[math.min(index + 2, route.length - 1)];

    double catmullRom(double a, double b, double c, double d) {
      final squared = local * local;
      final cubed = squared * local;
      return 0.5 *
          (2 * b +
              (-a + c) * local +
              (2 * a - 5 * b + 4 * c - d) * squared +
              (-a + 3 * b - 3 * c + d) * cubed);
    }

    return Offset(
      catmullRom(p0.dx, p1.dx, p2.dx, p3.dx),
      catmullRom(p0.dy, p1.dy, p2.dy, p3.dy),
    );
  }

  void _paintCoverImage(Canvas canvas, Size size, ui.Image image) {
    final fitted = applyBoxFit(
      BoxFit.cover,
      Size(image.width.toDouble(), image.height.toDouble()),
      size,
    );
    final source = Alignment.center.inscribe(
      fitted.source,
      Offset.zero & Size(image.width.toDouble(), image.height.toDouble()),
    );
    final destination = Alignment.center.inscribe(
      fitted.destination,
      Offset.zero & size,
    );
    canvas.drawImageRect(
      image,
      source,
      destination,
      Paint()..filterQuality = FilterQuality.high,
    );
  }

  @override
  bool shouldRepaint(covariant _StoryCharacterMovementPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.backgroundImage != backgroundImage ||
        oldDelegate.spriteSheetImage != spriteSheetImage ||
        oldDelegate.rows != rows ||
        oldDelegate.identityLockedMotion != identityLockedMotion ||
        oldDelegate.action != action ||
        oldDelegate.running != running ||
        oldDelegate.routeKey != routeKey;
  }
}
