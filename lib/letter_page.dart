import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'main.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/api_service.dart';

class LetterPage extends StatefulWidget {
  const LetterPage({super.key, required this.story});

  final StorySession story;

  @override
  State<LetterPage> createState() => _LetterPageState();
}

class _LetterPageState extends State<LetterPage> {
  final _controller = TextEditingController();
  late final List<StoryCharacter> _characters;
  late StoryCharacter _recipient;
  bool _isSending = false;
  String? _reply;

  @override
  void initState() {
    super.initState();
    _characters = _charactersFor(widget.story);
    _recipient = _characters.first;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  List<StoryCharacter> _charactersFor(StorySession story) {
    final cast = story.effectiveStoryCast;
    if (cast.isEmpty) {
      return const [
        StoryCharacter(
          name: '주인공',
          role: '이야기 속 친구',
          personality: '따뜻하고 용감한 마음을 지녔어요',
          greeting: '안녕! 네 편지를 기다리고 있었어.',
          avatarEmoji: '✨',
        ),
      ];
    }
    const emojis = ['🌟', '🦊', '🦉', '🐉', '🌿'];
    return List.generate(cast.length, (index) {
      final member = cast[index];
      final description = member.sourceDescription?.trim() ?? '';
      return StoryCharacter(
        name: member.name,
        role: member.role,
        personality: description.isEmpty ? '이야기 속에서 만난 소중한 친구예요' : description,
        greeting: '안녕! 네 편지를 기다리고 있었어.',
        avatarEmoji: emojis[index % emojis.length],
      );
    });
  }

  Future<void> _sendLetter() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isSending) return;
    setState(() {
      _isSending = true;
      _reply = null;
    });
    try {
      final answer = await ApiService.chatWithStoryCharacter(
        storyId: widget.story.storyId,
        storyTitle: widget.story.initialPrompt,
        storyText: widget.story.fullStoryText,
        age: widget.story.age,
        userName: context.read<AppState>().currentDisplayName,
        character: _recipient,
        messages: [CharacterChatMessage(role: 'user', content: '편지: $text')],
        userMessage: '나는 너에게 이런 편지를 썼어. 따뜻하게 답장해 줘.\n$text',
      );
      if (!mounted) return;
      setState(() => _reply = answer.reply);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _reply = '${_recipient.name}에게 편지를 전했어요. 다음에 다시 만나면 답장을 들려줄게요.';
      });
    } finally {
      if (mounted) setState(() => _isSending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(title: const Text('주인공에게 편지 쓰기')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Text(
                '동화 친구에게 마음을 전해 보세요',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 25,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '고마웠던 장면, 궁금했던 점, 응원하고 싶은 말을 자유롭게 적을 수 있어요.',
                style: TextStyle(color: AppColors.gray, height: 1.5),
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _characters.map((character) {
                  final selected = character.name == _recipient.name;
                  return ChoiceChip(
                    selected: selected,
                    onSelected: (_) => setState(() {
                      _recipient = character;
                      _reply = null;
                    }),
                    avatar: Text(character.avatarEmoji),
                    label: Text(character.name),
                    selectedColor: AppColors.p600,
                    backgroundColor: AppColors.card,
                    labelStyle: const TextStyle(color: Colors.white),
                    side: const BorderSide(color: AppColors.border),
                  );
                }).toList(),
              ),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.all(22),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFFFFF8E8), Color(0xFFF6E9CB)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: const Color(0xFFB98D53), width: 2),
                  boxShadow: const [
                    BoxShadow(
                      color: Colors.black26,
                      blurRadius: 20,
                      offset: Offset(0, 10),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'To. ${_recipient.name}',
                      style: const TextStyle(
                        color: Color(0xFF6B4423),
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const Divider(color: Color(0x336B4423), height: 26),
                    TextField(
                      controller: _controller,
                      minLines: 7,
                      maxLines: 11,
                      maxLength: 800,
                      style: const TextStyle(
                        color: Color(0xFF4A301C),
                        fontSize: 16,
                        height: 1.65,
                      ),
                      decoration: const InputDecoration(
                        hintText: '안녕, 나는 동화에서 네가 ... 했던 장면이 기억에 남아.\n',
                        hintStyle: TextStyle(color: Color(0x996B4423)),
                        border: InputBorder.none,
                        counterStyle: TextStyle(color: Color(0xFF8F6D48)),
                      ),
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: FilledButton.icon(
                        onPressed: _isSending ? null : _sendLetter,
                        icon: _isSending
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  color: Colors.white,
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.send_rounded),
                        label: Text(_isSending ? '전달 중...' : '편지 보내기'),
                        style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF8B3A2C),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (_reply != null) ...[
                const SizedBox(height: 22),
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppColors.card,
                    borderRadius: BorderRadius.circular(22),
                    border: Border.all(
                      color: AppColors.p500.withValues(alpha: 0.38),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'From. ${_recipient.name} ${_recipient.avatarEmoji}',
                        style: const TextStyle(
                          color: AppColors.p300,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        _reply!,
                        style: const TextStyle(
                          color: Colors.white,
                          height: 1.65,
                          fontSize: 15,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
