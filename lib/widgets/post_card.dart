import 'package:flutter/material.dart';

/// 커뮤니티 공통 색
const kCommunityBg = Color(0xFF070018);
const kCommunityCard = Color(0xFF140028);
const kCommunityPurple = Color(0xFF8B5CF6);

String communityDate(dynamic iso) {
  final d = DateTime.tryParse((iso ?? '').toString());
  if (d == null) return '';
  final local = d.isUtc ? d.toLocal() : DateTime.utc(d.year, d.month, d.day, d.hour, d.minute).toLocal();
  return '${local.year}.${local.month.toString().padLeft(2, '0')}.${local.day.toString().padLeft(2, '0')}';
}

/// 작성자 프로필 사진 (없으면 닉네임 첫 글자)
class AuthorAvatar extends StatelessWidget {
  final Map<String, dynamic>? author;
  final double radius;

  const AuthorAvatar({super.key, required this.author, this.radius = 16});

  @override
  Widget build(BuildContext context) {
    final url = (author?['profile_image_url'] ?? '').toString();
    final nickname = (author?['nickname'] ?? '친구').toString();
    return CircleAvatar(
      radius: radius,
      backgroundColor: Colors.purple.withOpacity(0.35),
      backgroundImage: url.isNotEmpty ? NetworkImage(url) : null,
      child: url.isNotEmpty
          ? null
          : Text(
              nickname.isNotEmpty ? nickname.characters.first : '?',
              style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: radius * 0.9),
            ),
    );
  }
}

class GenreChip extends StatelessWidget {
  final String genre;
  const GenreChip(this.genre, {super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.purple.withOpacity(0.2),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text('#$genre',
          style: const TextStyle(
              color: Colors.purpleAccent,
              fontWeight: FontWeight.bold,
              fontSize: 12)),
    );
  }
}

/// 게시글 목록 카드 (커뮤니티 목록 / 스크랩한 글 공통)
class PostCard extends StatelessWidget {
  final Map<String, dynamic> post;
  final VoidCallback onTap;

  const PostCard({super.key, required this.post, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final author = (post['author'] as Map?)?.cast<String, dynamic>();
    final genre = (post['genre'] ?? '').toString();
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: kCommunityCard,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(24),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  AuthorAvatar(author: author),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      author?['nickname'] ?? '친구',
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w600),
                    ),
                  ),
                  Text(communityDate(post['created_at']),
                      style: const TextStyle(color: Colors.white38, fontSize: 12)),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                post['title'] ?? '',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                    color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 6),
              Text(
                post['preview'] ?? '',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Colors.white60, height: 1.5),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  if (genre.isNotEmpty) GenreChip(genre),
                  const Spacer(),
                  const Icon(Icons.favorite, color: Colors.pinkAccent, size: 18),
                  const SizedBox(width: 4),
                  Text('${post['likes_count'] ?? 0}',
                      style: const TextStyle(color: Colors.white70)),
                  const SizedBox(width: 16),
                  const Icon(Icons.chat_bubble, color: Colors.lightBlueAccent, size: 18),
                  const SizedBox(width: 4),
                  Text('${post['comments_count'] ?? 0}',
                      style: const TextStyle(color: Colors.white70)),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
