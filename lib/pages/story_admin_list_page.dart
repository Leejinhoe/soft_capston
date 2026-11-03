import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';
import '../core/story_genres.dart';
import 'story_admin_detail_page.dart';

/// 관리자 > 동화 관리 (GET /api/admin/stories)
class StoryAdminListPage extends StatefulWidget {
  const StoryAdminListPage({super.key});

  @override
  State<StoryAdminListPage> createState() => _StoryAdminListPageState();
}

class _StoryAdminListPageState extends State<StoryAdminListPage> {
  static const _size = 30;

  final searchController = TextEditingController();
  List<Map<String, dynamic>> stories = [];
  bool isLoading = true;
  bool loadingMore = false;
  bool hasMore = false;
  int page = 1;
  int total = 0;
  String genre = '';

  @override
  void initState() {
    super.initState();
    loadStories();
  }

  @override
  void dispose() {
    searchController.dispose();
    super.dispose();
  }

  Future<void> loadStories({bool more = false}) async {
    setState(() => more ? loadingMore = true : isLoading = true);
    final nextPage = more ? page + 1 : 1;
    try {
      final q = Uri.encodeQueryComponent(searchController.text.trim());
      final g = Uri.encodeQueryComponent(genre);
      final response = await ApiClient.get(
          '/api/admin/stories?page=$nextPage&size=$_size&q=$q&genre=$g');
      if (!mounted) return;
      if (adminOk(context, response)) {
        final data = ApiClient.decode(response);
        final items = (data['items'] as List).cast<Map<String, dynamic>>();
        setState(() {
          stories = more ? [...stories, ...items] : items;
          page = nextPage;
          total = data['total'] ?? 0;
          hasMore = data['has_more'] == true;
        });
      }
    } catch (e) {
      if (mounted) adminToast(context, '동화 목록을 불러오지 못했어요: $e');
    }
    if (mounted) setState(() => isLoading = loadingMore = false);
  }

  Future<void> _openDetail(Map<String, dynamic> story) async {
    final deleted = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => StoryAdminDetailPage(storyId: story['id'])),
    );
    if (deleted == true) loadStories();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.bg,
      appBar: adminAppBar(isLoading ? '동화 관리' : '동화 관리 ($total개)'),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: AdminSearchField(
              controller: searchController,
              hint: '제목 또는 작성자',
              onSearch: loadStories,
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
            child: Row(
              children: [
                for (final g in ['', ...kStoryGenres])
                  adminChip(
                    label: g.isEmpty ? '전체' : g,
                    selected: genre == g,
                    onTap: () {
                      setState(() => genre = g);
                      loadStories();
                    },
                  ),
              ],
            ),
          ),
          Expanded(child: _list()),
        ],
      ),
    );
  }

  Widget _list() {
    if (isLoading) return adminLoading;
    if (stories.isEmpty) return adminEmpty('조건에 맞는 동화가 없어요.');
    return RefreshIndicator(
      onRefresh: loadStories,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: stories.length + (hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == stories.length) {
            return adminLoadMore(
                loading: loadingMore, onTap: () => loadStories(more: true));
          }
          return _card(stories[index]);
        },
      ),
    );
  }

  Widget _card(Map<String, dynamic> story) {
    final author = (story['author'] as Map?) ?? {};
    final bool shared = story['shared'] == true;
    final String g = (story['genre'] ?? '').toString();

    return GestureDetector(
      onTap: () => _openDetail(story),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AdminColors.card,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AdminColors.blue.withOpacity(0.25)),
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AdminColors.blue.withOpacity(0.15),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(Icons.menu_book, color: AdminColors.blue),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    story['title'] ?? '',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    author['exists'] == false
                        ? '탈퇴한 회원 (@${author['id']})'
                        : '${author['nickname']} (@${author['id']})',
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: author['exists'] == false ? Colors.white38 : Colors.white70,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (g.isNotEmpty) adminTag(g, AdminColors.purple),
                      adminTag(shared ? '🌐 공유됨' : '비공개',
                          shared ? AdminColors.green : Colors.white38),
                      Text(adminDate(story['created_at']),
                          style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ],
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white38, size: 16),
          ],
        ),
      ),
    );
  }
}
