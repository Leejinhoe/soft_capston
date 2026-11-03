import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/story_genres.dart';
import '../widgets/custom_bottom_nav.dart';
import '../widgets/post_card.dart';
import 'post_detail_page.dart';

/// 커뮤니티: 최신순 게시글 목록 + 장르 탭 + 제목/닉네임 검색 + 더보기
class BoardPage extends StatefulWidget {
  final String displayName;

  const BoardPage({
    super.key,
    required this.displayName,
  });

  @override
  State<BoardPage> createState() => _BoardPageState();
}

class _BoardPageState extends State<BoardPage> {
  static const _pageSize = 10;
  static const _allTab = '전체';

  final TextEditingController _searchController = TextEditingController();
  final List<String> _tabs = [_allTab, ...kStoryGenres];

  String _genre = _allTab;
  String _query = '';
  List<Map<String, dynamic>> _posts = [];
  int _page = 0;
  int _total = 0;
  bool _hasMore = false;
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String? _error;
  int _requestSeq = 0; // 탭을 빠르게 바꿀 때 늦게 온 예전 응답은 버립니다.

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  String _listPath(int page) {
    final params = <String, String>{
      'page': '$page',
      'size': '$_pageSize',
      if (_genre != _allTab) 'genre': _genre,
      if (_query.isNotEmpty) 'q': _query,
    };
    return Uri(path: '/api/community/posts', queryParameters: params).toString();
  }

  Future<void> _reload() async {
    final seq = ++_requestSeq;
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await ApiClient.get(_listPath(1));
      if (!mounted || seq != _requestSeq) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response) as Map<String, dynamic>;
        setState(() {
          _posts = (data['items'] as List).cast<Map<String, dynamic>>();
          _page = 1;
          _total = data['total'] ?? 0;
          _hasMore = data['has_more'] == true;
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = ApiClient.errorMessage(response);
          _isLoading = false;
        });
      }
    } catch (_) {
      if (!mounted || seq != _requestSeq) return;
      setState(() {
        _error = '서버에 연결하지 못했어요.';
        _isLoading = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (_isLoadingMore || !_hasMore) return;
    final seq = _requestSeq;
    setState(() => _isLoadingMore = true);
    try {
      final response = await ApiClient.get(_listPath(_page + 1));
      if (!mounted || seq != _requestSeq) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response) as Map<String, dynamic>;
        final more = (data['items'] as List).cast<Map<String, dynamic>>();
        final known = _posts.map((p) => p['id']).toSet();
        setState(() {
          _posts.addAll(more.where((p) => !known.contains(p['id'])));
          _page += 1;
          _total = data['total'] ?? _total;
          _hasMore = data['has_more'] == true;
        });
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (_) {
      if (mounted) _toast('서버에 연결하지 못했어요.');
    }
    if (mounted) setState(() => _isLoadingMore = false);
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  void _search() {
    FocusScope.of(context).unfocus();
    final q = _searchController.text.trim();
    if (q == _query) return;
    _query = q;
    _reload();
  }

  void _clearSearch() {
    _searchController.clear();
    if (_query.isEmpty) return;
    _query = '';
    _reload();
  }

  void _selectGenre(String genre) {
    if (genre == _genre) return;
    setState(() => _genre = genre);
    _reload();
  }

  Future<void> _openPost(Map<String, dynamic> post) async {
    final result = await Navigator.push<PostDetailResult>(
      context,
      MaterialPageRoute(builder: (_) => PostDetailPage(postId: post['id'])),
    );
    if (!mounted || result == null) return;
    setState(() {
      if (result.deleted) {
        _posts.removeWhere((p) => p['id'] == post['id']);
        _total = (_total - 1).clamp(0, 1 << 30);
      } else if (result.summary != null) {
        final i = _posts.indexWhere((p) => p['id'] == post['id']);
        if (i >= 0) _posts[i] = {..._posts[i], ...result.summary!};
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kCommunityBg,
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'board',
        displayName: widget.displayName,
      ),
      body: SafeArea(
        child: RefreshIndicator(
          color: Colors.purpleAccent,
          onRefresh: _reload,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
                sliver: SliverToBoxAdapter(child: _header()),
              ),
              SliverToBoxAdapter(child: _genreTabs()),
              ..._content(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _header() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '✨ 커뮤니티',
          style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 10),
        const Text(
          '다른 친구들의 이야기를 만나보세요',
          style: TextStyle(color: Colors.white70, fontSize: 16),
        ),
        const SizedBox(height: 22),
        TextField(
          controller: _searchController,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => _search(),
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: '제목이나 닉네임으로 찾아보세요',
            hintStyle: const TextStyle(color: Colors.white38),
            prefixIcon: const Icon(Icons.search, color: Colors.white54),
            suffixIcon: ValueListenableBuilder<TextEditingValue>(
              valueListenable: _searchController,
              builder: (_, value, _) => value.text.isEmpty
                  ? IconButton(
                      icon: const Icon(Icons.arrow_forward, color: Colors.purpleAccent),
                      onPressed: _search,
                    )
                  : IconButton(
                      icon: const Icon(Icons.close, color: Colors.white54),
                      onPressed: _clearSearch,
                    ),
            ),
            filled: true,
            fillColor: const Color(0xFF1A0B3A),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(20),
              borderSide: BorderSide.none,
            ),
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  Widget _genreTabs() {
    return SizedBox(
      height: 46,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        itemCount: _tabs.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final genre = _tabs[i];
          final selected = genre == _genre;
          return GestureDetector(
            onTap: () => _selectGenre(genre),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selected ? kCommunityPurple : const Color(0xFF1A0B3A),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white10),
              ),
              child: Text(
                genre,
                style: TextStyle(
                  color: selected ? Colors.white : Colors.white70,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  List<Widget> _content() {
    if (_isLoading) {
      return const [
        SliverFillRemaining(
          hasScrollBody: false,
          child: Center(child: CircularProgressIndicator(color: Colors.purpleAccent)),
        ),
      ];
    }
    if (_error != null) {
      return [
        SliverFillRemaining(
          hasScrollBody: false,
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(_error!, style: const TextStyle(color: Colors.white70)),
                TextButton(
                  onPressed: _reload,
                  child: const Text('다시 불러오기', style: TextStyle(color: Colors.purpleAccent)),
                ),
              ],
            ),
          ),
        ),
      ];
    }
    if (_posts.isEmpty) {
      final message = _query.isNotEmpty
          ? "'$_query'(으)로 찾은 이야기가 없어요.\n다른 말로 찾아볼까요? 🔍"
          : '아직 올라온 이야기가 없어요.\n동화를 만들고 첫 번째로 공유해 볼까요? 📖';
      return [
        SliverFillRemaining(
          hasScrollBody: false,
          child: Center(
            child: Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white54, fontSize: 16, height: 1.6),
            ),
          ),
        ),
      ];
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(24, 18, 24, 0),
        sliver: SliverToBoxAdapter(
          child: Text('이야기 $_total개',
              style: const TextStyle(color: Colors.white54, fontSize: 13)),
        ),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 0),
        sliver: SliverList.builder(
          itemCount: _posts.length,
          itemBuilder: (_, i) => PostCard(post: _posts[i], onTap: () => _openPost(_posts[i])),
        ),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 100),
        sliver: SliverToBoxAdapter(
          child: _hasMore
              ? OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.purpleAccent,
                    side: const BorderSide(color: Colors.purpleAccent),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  onPressed: _isLoadingMore ? null : _loadMore,
                  child: _isLoadingMore
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.purpleAccent))
                      : const Text('더보기', style: TextStyle(fontWeight: FontWeight.bold)),
                )
              : const Center(
                  child: Text('모든 이야기를 다 봤어요 🌙',
                      style: TextStyle(color: Colors.white38)),
                ),
        ),
      ),
    ];
  }
}
