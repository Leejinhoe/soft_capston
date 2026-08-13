import 'package:fairytale_hyeonlim_merged/widgets/story_character_animation.dart';
import 'package:flutter/material.dart';

void main() {
  runApp(const StoryAnimationPreviewApp());
}

class StoryAnimationPreviewApp extends StatelessWidget {
  const StoryAnimationPreviewApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true),
      home: Scaffold(
        backgroundColor: Color(0xff101427),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 960),
              child: const StoryCharacterAnimation(
                characterKey: 'male_01',
                storyText: 'Mino runs toward the glowing castle.',
                genre: 'fantasy',
              ),
            ),
          ),
        ),
      ),
    );
  }
}
