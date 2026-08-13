import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

import 'package:fairytale_hyeonlim_merged/models/story_video.dart';
import 'package:fairytale_hyeonlim_merged/widgets/story_video_player.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  final clip = StoryVideoCatalog.forChapter(
    text: '',
    choice: '\ubcf4\ubb3c\uc0c1\uc790\ub97c \uc5f4\uc5b4\ubcf8\ub2e4',
    chapter: 2,
    genre: '\ud310\ud0c0\uc9c0',
    characterKey: 'male_01',
  )!;
  runApp(StoryVideoPreviewApp(clip: clip));
}

class StoryVideoPreviewApp extends StatelessWidget {
  final StoryVideoClip clip;

  const StoryVideoPreviewApp({super.key, required this.clip});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true),
      home: Scaffold(
        backgroundColor: const Color(0xff06041a),
        appBar: AppBar(
          title: const Text(
              '\uc120\ud0dd \ud6c4 \ub3d9\uc601\uc0c1 \ubbf8\ub9ac\ubcf4\uae30'),
          backgroundColor: const Color(0xff06041a),
        ),
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 960),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '\uc120\ud0dd: \ubcf4\ubb3c\uc0c1\uc790\ub97c \uc5f4\uc5b4\ubcf8\ub2e4',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 14),
                  StoryVideoPlayer(clip: clip),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
