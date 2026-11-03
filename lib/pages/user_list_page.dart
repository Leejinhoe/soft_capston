import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';
import 'user_detail_page.dart';

const userStatusLabels = {'active': '활동', 'banned': '정지'};

/// 관리자 > 회원 관리 (GET /api/admin/users)
class UserListPage extends StatefulWidget {
  const UserListPage({super.key});

  @override
  State<UserListPage> createState() => _UserListPageState();
}

class _UserListPageState extends State<UserListPage> {
  static const _filters = [('', '전체'), ('active', '활동'), ('banned', '정지')];
  static const _size = 30;

  final searchController = TextEditingController();
  List<Map<String, dynamic>> users = [];
  bool isLoading = true;
  bool loadingMore = false;
  bool hasMore = false;
  int page = 1;
  int total = 0;
  String status = '';

  @override
  void initState() {
    super.initState();
    loadUsers();
  }

  @override
  void dispose() {
    searchController.dispose();
    super.dispose();
  }

  Future<void> loadUsers({bool more = false}) async {
    setState(() => more ? loadingMore = true : isLoading = true);
    final nextPage = more ? page + 1 : 1;
    try {
      final q = Uri.encodeQueryComponent(searchController.text.trim());
      final response = await ApiClient.get(
          '/api/admin/users?page=$nextPage&size=$_size&q=$q${status.isEmpty ? '' : '&status=$status'}');
      if (!mounted) return;
      if (adminOk(context, response)) {
        final data = ApiClient.decode(response);
        final items = (data['items'] as List).cast<Map<String, dynamic>>();
        setState(() {
          users = more ? [...users, ...items] : items;
          page = nextPage;
          total = data['total'] ?? 0;
          hasMore = data['has_more'] == true;
        });
      }
    } catch (e) {
      if (mounted) adminToast(context, '회원 목록을 불러오지 못했어요: $e');
    }
    if (mounted) setState(() => isLoading = loadingMore = false);
  }

  Future<void> _openDetail(Map<String, dynamic> user) async {
    final changed = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => UserDetailPage(user: user)),
    );
    if (changed == true) loadUsers();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.bg,
      appBar: adminAppBar(isLoading ? '회원 관리' : '회원 관리 ($total명)'),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: AdminSearchField(
              controller: searchController,
              hint: '아이디 · 닉네임 · 이름 · 이메일',
              onSearch: loadUsers,
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
            child: Row(
              children: [
                for (final f in _filters)
                  adminChip(
                    label: f.$2,
                    selected: status == f.$1,
                    onTap: () {
                      setState(() => status = f.$1);
                      loadUsers();
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
    if (users.isEmpty) return adminEmpty('조건에 맞는 회원이 없어요.');
    return RefreshIndicator(
      onRefresh: loadUsers,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: users.length + (hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == users.length) {
            return adminLoadMore(
                loading: loadingMore, onTap: () => loadUsers(more: true));
          }
          return _card(users[index]);
        },
      ),
    );
  }

  Widget _card(Map<String, dynamic> user) {
    final bool banned = user['status'] == 'banned';
    final bool isAdmin = user['role'] == 'admin';
    final int warnings = user['warning_count'] ?? 0;
    final String email = (user['email'] ?? '').toString();
    final String provider = (user['provider'] ?? '').toString();

    return GestureDetector(
      onTap: () => _openDetail(user),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AdminColors.card,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: banned
                ? AdminColors.red.withOpacity(0.5)
                : AdminColors.purple.withOpacity(0.2),
          ),
        ),
        child: Row(
          children: [
            CircleAvatar(
              radius: 24,
              backgroundColor: banned ? Colors.white12 : AdminColors.purple,
              child: Icon(isAdmin ? Icons.admin_panel_settings : Icons.person,
                  color: Colors.white),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          user['nickname'] ?? '',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text('@${user['id']}',
                          style: const TextStyle(
                              color: Colors.white54, fontSize: 13)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    [
                      if ((user['name'] ?? '').toString().isNotEmpty) user['name'],
                      email.isEmpty ? '이메일 없음' : email,
                    ].join(' · '),
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      adminTag(userStatusLabels[user['status']] ?? '활동',
                          banned ? AdminColors.red : AdminColors.green),
                      if (isAdmin) adminTag('관리자', AdminColors.purple),
                      if (warnings > 0) adminTag('경고 $warnings회', AdminColors.orange),
                      if (provider.isNotEmpty) adminTag(provider, Colors.white54),
                      Text('가입 ${adminDate(user['created_at'], withTime: false)}',
                          style: const TextStyle(
                              color: Colors.white38, fontSize: 12)),
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
