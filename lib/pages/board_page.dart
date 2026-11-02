import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import '../widgets/custom_bottom_nav.dart';

class BoardPage extends StatefulWidget {
  final String userId;
  final String displayName;

  const BoardPage({
    super.key,
    this.userId = 'user123',
    required this.displayName,
  });

  @override
  State<BoardPage> createState() => _BoardPageState();
}

class _BoardPageState extends State<BoardPage> {
  Widget storyCard({
    required String title,
    required String author,
    required String image,
    required String tag,
    required int likes,
    required int comments,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 22),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(26),
        border: Border.all(
          color: Colors.white10,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 이미지
          ClipRRect(
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(26),
            ),
            child: Image.network(
              image,
              height: 190,
              width: double.infinity,
              fit: BoxFit.cover,
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'by $author',
                  style: const TextStyle(
                    color: Colors.white54,
                  ),
                ),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.purple.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    tag,
                    style: const TextStyle(
                      color: Colors.purpleAccent,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    const Icon(
                      Icons.favorite,
                      color: Colors.pinkAccent,
                      size: 20,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      '$likes',
                      style: const TextStyle(
                        color: Colors.white70,
                      ),
                    ),
                    const SizedBox(width: 20),
                    const Icon(
                      Icons.chat_bubble,
                      color: Colors.lightBlueAccent,
                      size: 20,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      '$comments',
                      style: const TextStyle(
                        color: Colors.white70,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(
                        Icons.report,
                        color: Colors.redAccent,
                      ),
                      onPressed: () {
                        showDialog(
                          context: context,
                          builder: (_) => AlertDialog(
                            title: const Text("🚨 신고하기"),
                            content: Text("'$title' 게시글을 신고하시겠습니까?"),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.pop(context);
                                },
                                child: const Text("취소"),
                              ),
                              ElevatedButton(
                                onPressed: () async {
                                  Navigator.pop(context);
                                  await reportStory(author, title);
                                },
                                child: const Text("신고"),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'board',
        userId: widget.userId,
        displayName: widget.displayName,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 10),
              const Text(
                '✨ 커뮤니티',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 34,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                '다른 친구들의 이야기를 만나보세요',
                style: TextStyle(
                  color: Colors.white70,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 30),
              storyCard(
                title: '달빛 토끼의 모험',
                author: '민지',
                image:
                'https://images.unsplash.com/photo-1518791841217-8f162f1e1131',
                tag: '#판타지',
                likes: 24,
                comments: 8,
              ),
              storyCard(
                title: '용감한 꼬마 마법사',
                author: '준호',
                image:
                'https://images.unsplash.com/photo-1506744038136-46273834b3fb',
                tag: '#모험',
                likes: 18,
                comments: 5,
              ),
              storyCard(
                title: '하늘을 나는 고래',
                author: '서아',
                image:
                'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee',
                tag: '#감성',
                likes: 31,
                comments: 12,
              ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> reportStory(String author, String title) async {
    try {
      final response = await http.post(
        Uri.parse("http://127.0.0.1:8000/report"),
        headers: {
          "Content-Type": "application/json",
        },
        body: jsonEncode({
          "reporter": widget.displayName,
          "reporter_id": widget.userId,
          "author": author,
          "story_title": title,
          "reason": "부적절한 내용",
        }),
      );

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("신고가 접수되었습니다."),
            ),
          );
        }
      }
    } catch (e) {
      debugPrint('신고 처리 에러: $e');
    }
  }
}