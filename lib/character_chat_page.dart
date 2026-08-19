import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'main.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/api_service.dart';

class CharacterChatPage extends StatefulWidget {
  final StorySession story;

  const CharacterChatPage({
    super.key,
    required this.story,
  });

  @override
  State<CharacterChatPage> createState() => _CharacterChatPageState();
}

class _CharacterChatPageState extends State<CharacterChatPage> {
  static const _initialSuggestions = [
    '모험에서 가장 기억나는 순간은 뭐야?',
    '그때 어떤 기분이었어?',
    '나에게 해 주고 싶은 말이 있어?',
  ];

  final TextEditingController _messageController = TextEditingController();
  final ScrollController _messageScrollController = ScrollController();
  final Map<String, List<CharacterChatMessage>> _conversations = {};
  final Map<String, List<String>> _suggestions = {};

  List<StoryCharacter> _characters = const [];
  StoryCharacter? _selectedCharacter;
  bool _isLoadingCharacters = true;
  bool _isSending = false;
  String? _notice;

  @override
  void initState() {
    super.initState();
    unawaited(_loadCharacters());
  }

  @override
  void dispose() {
    _messageController.dispose();
    _messageScrollController.dispose();
    super.dispose();
  }

  Future<void> _loadCharacters({bool forceFallback = false}) async {
    setState(() {
      _isLoadingCharacters = true;
      _notice = null;
    });

    List<StoryCharacter> characters;
    try {
      if (forceFallback || widget.story.storyId.startsWith('mock_')) {
        throw const _UseLocalCharacters();
      }
      characters = await ApiService.discoverStoryCharacters(
        storyId: widget.story.storyId,
        storyTitle: widget.story.initialPrompt,
        storyText: widget.story.fullStoryText,
        age: widget.story.age,
      );
    } on _UseLocalCharacters {
      characters = _fallbackCharacters(widget.story);
      _notice = '임시 동화의 등장인물로 대화를 준비했어요.';
    } catch (_) {
      characters = _fallbackCharacters(widget.story);
      _notice = 'AI 서버에 연결하지 못해 동화 본문에서 찾은 캐릭터를 보여드려요.';
    }

    if (!mounted) return;
    setState(() {
      _characters = characters;
      _selectedCharacter = characters.isEmpty ? null : characters.first;
      _isLoadingCharacters = false;
      final selected = _selectedCharacter;
      if (selected != null) _ensureConversation(selected);
    });
    _scrollToLatest();
  }

  void _ensureConversation(StoryCharacter character) {
    _conversations.putIfAbsent(
      character.name,
      () => [
        CharacterChatMessage(
          role: 'character',
          content: character.greeting.isNotEmpty
              ? character.greeting
              : '안녕! 나는 ${character.name}이야. 우리 이야기에서 궁금했던 걸 편하게 물어봐.',
        ),
      ],
    );
    _suggestions.putIfAbsent(
      character.name,
      () => List<String>.from(_initialSuggestions),
    );
  }

  void _selectCharacter(StoryCharacter character) {
    if (_isSending || character.name == _selectedCharacter?.name) return;
    setState(() {
      _selectedCharacter = character;
      _ensureConversation(character);
      _notice = null;
    });
    _scrollToLatest();
  }

  Future<void> _sendMessage([String? preset]) async {
    final character = _selectedCharacter;
    final message = (preset ?? _messageController.text).trim();
    if (character == null || message.isEmpty || _isSending) return;

    final conversation = _conversations[character.name]!;
    setState(() {
      conversation.add(CharacterChatMessage(role: 'user', content: message));
      _messageController.clear();
      _isSending = true;
      _notice = null;
    });
    _scrollToLatest();

    CharacterChatReply result;
    try {
      if (widget.story.storyId.startsWith('mock_')) {
        throw const _UseLocalCharacters();
      }
      result = await ApiService.chatWithStoryCharacter(
        storyId: widget.story.storyId,
        storyTitle: widget.story.initialPrompt,
        storyText: widget.story.fullStoryText,
        age: widget.story.age,
        userName: context.read<AppState>().currentDisplayName,
        character: character,
        messages: List<CharacterChatMessage>.from(conversation),
        userMessage: message,
      );
    } catch (_) {
      result = _fallbackReply(character, message);
      _notice = '서버 답장을 받지 못해 캐릭터의 임시 답변을 보여드려요.';
    }

    if (!mounted || _selectedCharacter?.name != character.name) return;
    setState(() {
      conversation.add(
        CharacterChatMessage(role: 'character', content: result.reply),
      );
      _suggestions[character.name] = result.suggestedReplies.isNotEmpty
          ? result.suggestedReplies
          : List<String>.from(_initialSuggestions);
      _isSending = false;
    });
    _scrollToLatest();
  }

  CharacterChatReply _fallbackReply(
    StoryCharacter character,
    String message,
  ) {
    final normalized = message.replaceAll(RegExp(r'\s+'), ' ');
    late String reply;
    if (RegExp(r'기분|마음|무서|두려').hasMatch(normalized)) {
      reply = '솔직히 조금 떨렸지만 혼자가 아니라는 생각에 힘이 났어. '
          '우리 이야기에서 용기를 낼 수 있었던 건 곁에 있는 친구들의 마음 덕분이야.';
    } else if (RegExp(r'왜|이유|어째서').hasMatch(normalized)) {
      reply = '그때는 내가 소중하게 생각하는 것을 지키고 싶었어. '
          '서두르기보다 친구들의 이야기를 듣고 움직이는 게 좋은 방법이라는 것도 배웠지.';
    } else if (RegExp(r'친구|좋아|고마').hasMatch(normalized)) {
      reply = '그렇게 말해 줘서 정말 고마워! 너도 내 이야기 속에 함께 있었다면 든든한 친구가 되었을 거야.';
    } else {
      reply = '${character.name}인 내가 듣기에도 참 재미있는 질문이야. '
          '나는 ${character.personality.replaceAll(RegExp(r'[.!?]+$'), '')} 마음으로 그 순간을 지나왔어. '
          '너라면 우리 이야기에서 어떤 길을 골랐을지 궁금해!';
    }
    return CharacterChatReply(
      reply: reply,
      suggestedReplies: const [
        '다시 모험한다면 무엇을 하고 싶어?',
        '가장 고마웠던 친구는 누구야?',
        '나도 용기를 내려면 어떻게 해야 해?',
      ],
    );
  }

  void _resetCurrentConversation() {
    final character = _selectedCharacter;
    if (character == null || _isSending) return;
    setState(() {
      _conversations.remove(character.name);
      _suggestions.remove(character.name);
      _ensureConversation(character);
      _notice = '${character.name}와 새 대화를 시작했어요.';
    });
    _scrollToLatest();
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_messageScrollController.hasClients) return;
      _messageScrollController.animateTo(
        _messageScrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 320),
        curve: Curves.easeOutCubic,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final character = _selectedCharacter;
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        titleSpacing: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('이야기 속 친구와 대화'),
            Text(
              widget.story.initialPrompt,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.gray,
                fontSize: 10,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: '현재 대화 새로 시작',
            onPressed: character == null ? null : _resetCurrentConversation,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Stack(
        children: [
          const Positioned.fill(child: _ChatBackground()),
          SafeArea(
            top: false,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 920),
                child: _isLoadingCharacters
                    ? _buildLoadingCharacters()
                    : Column(
                        children: [
                          _buildCharacterPicker(),
                          if (_notice != null) _buildNotice(_notice!),
                          Expanded(
                            child: character == null
                                ? _buildNoCharacter()
                                : _buildConversation(character),
                          ),
                          if (character != null) _buildComposer(character),
                        ],
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingCharacters() {
    return Center(
      child: Container(
        margin: const EdgeInsets.all(24),
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 26),
        decoration: BoxDecoration(
          color: AppColors.card.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: AppColors.border),
        ),
        child: const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: AppColors.p400, strokeWidth: 2),
            SizedBox(height: 18),
            Text(
              '동화 속 친구들을 만나고 있어요...',
              style:
                  TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCharacterPicker() {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 12),
      decoration: BoxDecoration(
        color: AppColors.bg2.withValues(alpha: 0.92),
        border: const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.groups_2_rounded, color: AppColors.p300, size: 18),
              SizedBox(width: 8),
              Text(
                '누구와 이야기할까요?',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 105,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _characters.length,
              separatorBuilder: (_, __) => const SizedBox(width: 10),
              itemBuilder: (context, index) {
                final character = _characters[index];
                return _buildCharacterCard(character);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCharacterCard(StoryCharacter character) {
    final selected = character.name == _selectedCharacter?.name;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _selectCharacter(character),
        borderRadius: BorderRadius.circular(18),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          width: 170,
          padding: const EdgeInsets.all(11),
          decoration: BoxDecoration(
            gradient: selected
                ? const LinearGradient(
                    colors: [Color(0xFF5B21B6), Color(0xFF9D3F78)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  )
                : null,
            color: selected ? null : AppColors.card,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? AppColors.p300 : Colors.white12,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: AppColors.p600.withValues(alpha: 0.28),
                      blurRadius: 16,
                      offset: const Offset(0, 6),
                    ),
                  ]
                : null,
          ),
          child: Row(
            children: [
              Container(
                width: 43,
                height: 43,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: selected ? 0.16 : 0.08),
                  shape: BoxShape.circle,
                ),
                child: Text(character.avatarEmoji,
                    style: const TextStyle(fontSize: 24)),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      character.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      character.role,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.72),
                        fontSize: 10,
                        height: 1.25,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNotice(String message) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: const Color(0xFF2B2348).withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.p500.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline_rounded,
              color: AppColors.p300, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: AppColors.p300, fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConversation(StoryCharacter character) {
    final messages = _conversations[character.name] ?? const [];
    return Column(
      children: [
        Container(
          width: double.infinity,
          margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: const Color(0xFF191334).withValues(alpha: 0.88),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.white10),
          ),
          child: Row(
            children: [
              Text(character.avatarEmoji, style: const TextStyle(fontSize: 29)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${character.name} · ${character.role}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      character.personality,
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
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                decoration: BoxDecoration(
                  color: AppColors.teal.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Text(
                  '동화 기억 중',
                  style: TextStyle(
                    color: AppColors.teal,
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            controller: _messageScrollController,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 18),
            itemCount: messages.length + (_isSending ? 1 : 0),
            itemBuilder: (context, index) {
              if (_isSending && index == messages.length) {
                return _buildTypingBubble(character);
              }
              return _buildMessageBubble(character, messages[index]);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildMessageBubble(
    StoryCharacter character,
    CharacterChatMessage message,
  ) {
    final isUser = message.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (!isUser) ...[
              Container(
                width: 32,
                height: 32,
                alignment: Alignment.center,
                decoration: const BoxDecoration(
                  color: Color(0xFF2A2050),
                  shape: BoxShape.circle,
                ),
                child: Text(character.avatarEmoji,
                    style: const TextStyle(fontSize: 18)),
              ),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: Container(
                constraints: const BoxConstraints(maxWidth: 600),
                padding:
                    const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
                decoration: BoxDecoration(
                  gradient: isUser
                      ? const LinearGradient(
                          colors: [AppColors.p600, Color(0xFF9D3F78)],
                        )
                      : null,
                  color: isUser ? null : const Color(0xFF211A40),
                  borderRadius: BorderRadius.only(
                    topLeft: const Radius.circular(18),
                    topRight: const Radius.circular(18),
                    bottomLeft: Radius.circular(isUser ? 18 : 5),
                    bottomRight: Radius.circular(isUser ? 5 : 18),
                  ),
                  border: isUser ? null : Border.all(color: Colors.white10),
                ),
                child: Text(
                  message.content,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    height: 1.52,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypingBubble(StoryCharacter character) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: Color(0xFF2A2050),
                shape: BoxShape.circle,
              ),
              child: Text(character.avatarEmoji,
                  style: const TextStyle(fontSize: 18)),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFF211A40),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: Colors.white10),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      color: AppColors.p300,
                      strokeWidth: 2,
                    ),
                  ),
                  SizedBox(width: 9),
                  Text(
                    '이야기를 떠올리는 중...',
                    style: TextStyle(color: AppColors.gray, fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildComposer(StoryCharacter character) {
    final suggestions = _suggestions[character.name] ?? _initialSuggestions;
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
      decoration: BoxDecoration(
        color: AppColors.bg2.withValues(alpha: 0.98),
        border: const Border(top: BorderSide(color: AppColors.border)),
        boxShadow: const [
          BoxShadow(
              color: Colors.black38, blurRadius: 20, offset: Offset(0, -5)),
        ],
      ),
      child: Column(
        children: [
          SizedBox(
            height: 34,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: suggestions.length,
              separatorBuilder: (_, __) => const SizedBox(width: 7),
              itemBuilder: (context, index) {
                final suggestion = suggestions[index];
                return ActionChip(
                  onPressed: _isSending ? null : () => _sendMessage(suggestion),
                  avatar: const Icon(
                    Icons.auto_awesome_rounded,
                    color: AppColors.p300,
                    size: 13,
                  ),
                  label: Text(suggestion),
                  labelStyle:
                      const TextStyle(color: AppColors.p300, fontSize: 10),
                  backgroundColor: const Color(0xFF241B45),
                  disabledColor: const Color(0xFF19152D),
                  side:
                      BorderSide(color: AppColors.p500.withValues(alpha: 0.25)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(999),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: _messageController,
                  enabled: !_isSending,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: 300,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _sendMessage(),
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: '${character.name}에게 궁금한 것을 물어보세요',
                    hintStyle:
                        const TextStyle(color: AppColors.gray2, fontSize: 12),
                    counterText: '',
                    filled: true,
                    fillColor: const Color(0xFF17122F),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 13,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(17),
                      borderSide: BorderSide.none,
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(17),
                      borderSide: const BorderSide(color: AppColors.p500),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 9),
              IconButton.filled(
                tooltip: '메시지 보내기',
                onPressed: _isSending ? null : () => _sendMessage(),
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.p600,
                  disabledBackgroundColor: AppColors.card2,
                  minimumSize: const Size(48, 48),
                ),
                icon:
                    const Icon(Icons.arrow_upward_rounded, color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 7),
          const Text(
            '캐릭터 답변은 동화 기반 AI 역할극이며 실제 사람의 말이 아니에요.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.gray2, fontSize: 9),
          ),
        ],
      ),
    );
  }

  Widget _buildNoCharacter() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('📖', style: TextStyle(fontSize: 44)),
            const SizedBox(height: 12),
            const Text(
              '동화 속 친구를 찾지 못했어요.',
              style:
                  TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: () => _loadCharacters(forceFallback: true),
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('다시 찾아보기'),
            ),
          ],
        ),
      ),
    );
  }

  List<StoryCharacter> _fallbackCharacters(StorySession story) {
    final text = story.fullStoryText;
    final counts = <String, int>{};
    final patterns = [
      RegExp(r'([가-힣]{1,8}?)(?:이|가|은|는)\s*(?:말했|물었|대답|외쳤|웃었|생각했|고개를)'),
      RegExp(r'[“"]([가-힣]{1,8}?)(?:아|야)[,!?.…]'),
    ];
    const ignored = {
      '그때',
      '오늘',
      '마음',
      '친구',
      '모두',
      '누구',
      '주변',
      '이야기',
      '아이',
      '사람',
    };
    for (final pattern in patterns) {
      for (final match in pattern.allMatches(text)) {
        final name = match.group(1)?.trim() ?? '';
        if (name.length < 2 || ignored.contains(name)) continue;
        counts.update(name, (value) => value + 1, ifAbsent: () => 1);
      }
    }

    final names = counts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final selectedNames = names.take(4).map((entry) => entry.key).toList();
    if (selectedNames.isEmpty) {
      selectedNames.addAll(_knownCharacterNames(text));
    }
    if (selectedNames.isEmpty) selectedNames.add('이야기 속 주인공');

    return selectedNames.asMap().entries.map((entry) {
      final name = entry.value;
      final role = _roleFor(name, text, isFirst: entry.key == 0);
      return StoryCharacter(
        name: name,
        role: role,
        personality: entry.key == 0
            ? '용기 있게 길을 찾고 친구의 마음을 소중히 여겨요.'
            : '이야기 속 경험을 기억하며 다정하게 이야기해요.',
        greeting: '안녕! 나는 $name이야. 우리 동화에서 궁금했던 장면이 있니?',
        avatarEmoji: _emojiFor(name, role),
      );
    }).toList();
  }

  List<String> _knownCharacterNames(String text) {
    const known = {
      '별이': '별이',
      '토끼': '작은 토끼',
      '여우': '여우 친구',
      '요정': '숲의 요정',
      '공주': '공주',
      '왕자': '왕자',
      '용': '용 친구',
      '부엉이': '부엉이',
      '나비': '별나비',
    };
    return known.entries
        .where((entry) => text.contains(entry.key))
        .map((entry) => entry.value)
        .take(4)
        .toList();
  }

  String _roleFor(String name, String text, {required bool isFirst}) {
    if (name.contains('공주')) return '도움을 기다리던 공주';
    if (name.contains('용')) return '이야기의 용';
    if (name.contains('요정')) return '마법을 아는 안내자';
    if (name.contains('여우') || name.contains('친구')) return '함께한 동료';
    if (text.contains('$name에게 도움')) return '도움을 준 친구';
    return isFirst ? '이야기의 주인공' : '이야기 속 친구';
  }

  String _emojiFor(String name, String role) {
    final value = '$name $role';
    if (value.contains('공주')) return '👑';
    if (value.contains('왕자')) return '🤴';
    if (value.contains('용')) return '🐉';
    if (value.contains('토끼')) return '🐰';
    if (value.contains('여우')) return '🦊';
    if (value.contains('요정')) return '🧚';
    if (value.contains('부엉이')) return '🦉';
    if (value.contains('나비')) return '🦋';
    if (value.contains('별')) return '⭐';
    return role.contains('주인공') ? '🧒' : '✨';
  }
}

class _ChatBackground extends StatelessWidget {
  const _ChatBackground();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF08051B), Color(0xFF120B2B), Color(0xFF09061D)],
        ),
      ),
    );
  }
}

class _UseLocalCharacters implements Exception {
  const _UseLocalCharacters();
}
