import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../widgets/post_card.dart';
import 'post_detail_page.dart';

/// 마이페이지 > 스크랩한 글 (최근에 스크랩한 순)
class ScrapListPage extends StatefulWidget {
  const ScrapListPage({super.key});

  @override
  State<ScrapListPage> createState() => _ScrapListPageState();
}

class _ScrapListPageState extends State<ScrapListPage> {
  List<Map<String, dynamic>> _posts = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await ApiClient.get('/api/users/me/scraps');
      if (!mounted) return;
      setState(() {
        if (response.statusCode == 200) {
          _posts = (ApiClient.decode(response) as List).cast<Map<String, dynamic>>();
        } else {
          _error = ApiClient.errorMessage(response);
        }
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = '서버에 연결하지 못했어요.';
        _isLoading = false;
      });
    }
  }

  Future<void> _open(Map<String, dynamic> post) async {
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => PostDetailPage(postId: post['id'])),
    );
    // 상세에서 스크랩을 풀었거나 글이 지워졌을 수 있으니 다시 불러옵니다.
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kCommunityBg,
      appBar: AppBar(
        backgroundColor: kCommunityBg,
        foregroundColor: Colors.white,
        title: const Text('스크랩한 글'),
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: Colors.purpleAccent));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!, style: const TextStyle(color: Colors.white70)),
            TextButton(
              onPressed: _load,
              child: const Text('다시 불러오기', style: TextStyle(color: Colors.purpleAccent)),
            ),
          ],
        ),
      );
    }
    if (_posts.isEmpty) {
      return const Center(
        child: Text(
          '아직 스크랩한 글이 없어요.\n마음에 드는 이야기를 📌 스크랩해 보세요!',
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white54, fontSize: 16, height: 1.6),
        ),
      );
    }
    return RefreshIndicator(
      color: Colors.purpleAccent,
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(20),
        itemCount: _posts.length,
        itemBuilder: (_, i) => PostCard(post: _posts[i], onTap: () => _open(_posts[i])),
      ),
    );
  }
}
