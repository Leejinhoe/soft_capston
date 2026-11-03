import 'package:flutter/material.dart';
import '../core/admin_ui.dart';
import '../core/api_client.dart';

/// 관리자 > 회원 상세 (GET /api/admin/users/{id})
/// 경고 / 정지·해제 / 강제 탈퇴. 바뀐 게 있으면 목록에 true를 돌려줍니다.
class UserDetailPage extends StatefulWidget {
  final Map user; // 목록에서 받은 기본 정보 (id 필수)

  const UserDetailPage({super.key, required this.user});

  @override
  State<UserDetailPage> createState() => _UserDetailPageState();
}

class _UserDetailPageState extends State<UserDetailPage> {
  Map<String, dynamic>? detail;
  bool isLoading = true;
  bool busy = false;
  bool changed = false;

  String get userId => widget.user['id'].toString();
  String get _path => '/api/admin/users/${Uri.encodeComponent(userId)}';

  @override
  void initState() {
    super.initState();
    loadDetail();
  }

  Future<void> loadDetail() async {
    try {
      final response = await ApiClient.get(_path);
      if (!mounted) return;
      if (adminOk(context, response)) {
        setState(() => detail = Map<String, dynamic>.from(ApiClient.decode(response)));
      }
    } catch (e) {
      if (mounted) adminToast(context, '회원 정보를 불러오지 못했어요: $e');
    }
    if (mounted) setState(() => isLoading = false);
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() => busy = true);
    try {
      await action();
    } catch (e) {
      if (mounted) adminToast(context, '통신 오류가 발생했어요: $e');
    }
    if (mounted) setState(() => busy = false);
  }

  // ---------- 경고 ----------
  Future<void> giveWarning() async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AdminColors.card,
        title: const Text('경고 주기',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 200,
          maxLines: 3,
          style: const TextStyle(color: Colors.white),
          decoration: adminInputDecoration('경고 사유 (회원 알림함에 보여요)'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.orange, foregroundColor: Colors.white),
            child: const Text('경고하기'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null) return;
    if (reason.isEmpty) {
      if (mounted) adminToast(context, '경고 사유를 입력해 주세요.');
      return;
    }
    await _run(() async {
      final response = await ApiClient.post('$_path/warnings', body: {'reason': reason});
      if (!mounted || !adminOk(context, response)) return;
      changed = true;
      adminToast(context, '경고를 부여했어요. (누적 ${ApiClient.decode(response)['warning_count']}회)');
      await loadDetail();
    });
  }

  // ---------- 정지 / 해제 ----------
  Future<void> toggleBan() async {
    final banned = detail?['status'] == 'banned';
    final ok = await adminConfirm(
      context,
      title: banned ? '정지 해제' : '이용 정지',
      message: banned
          ? "'${detail?['nickname']}'님의 정지를 풀까요?\n다시 로그인해서 이용할 수 있어요."
          : "'${detail?['nickname']}'님을 정지할까요?\n바로 로그아웃되고 로그인할 수 없어요.",
      okText: banned ? '해제하기' : '정지하기',
      okColor: banned ? AdminColors.green : AdminColors.red,
    );
    if (!ok) return;
    await _run(() async {
      final response = await ApiClient.patch('$_path/status',
          body: {'status': banned ? 'active' : 'banned'});
      if (!mounted || !adminOk(context, response)) return;
      changed = true;
      adminToast(context, banned ? '정지를 해제했어요.' : '이용을 정지했어요.');
      await loadDetail();
    });
  }

  // ---------- 강제 탈퇴 (팝업 2번: 처리 방법 선택 → 최종 확인) ----------
  Future<void> forceDelete() async {
    final storyCount = detail?['story_count'] ?? 0;
    bool deleteStories = false;

    final step1 = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) {
          Widget option(bool value, String title, String sub) => RadioListTile<bool>(
                value: value,
                groupValue: deleteStories,
                onChanged: (v) => setLocal(() => deleteStories = v ?? false),
                activeColor: AdminColors.red,
                contentPadding: EdgeInsets.zero,
                title: Text(title, style: const TextStyle(color: Colors.white)),
                subtitle: Text(sub, style: const TextStyle(color: Colors.white54, fontSize: 12)),
              );
          return AlertDialog(
            backgroundColor: AdminColors.card,
            title: const Text('강제 탈퇴 (1/2)',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  "'${detail?['nickname']}'님을 탈퇴시킬까요?\n"
                  "게시글 ${detail?['post_count'] ?? 0}개와 댓글 ${detail?['comment_count'] ?? 0}개는 삭제돼요.",
                  style: const TextStyle(color: Colors.white70, height: 1.5),
                ),
                const SizedBox(height: 12),
                Text('만든 동화 $storyCount개는 어떻게 할까요?',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                option(false, '동화는 남기기', '작성자는 "탈퇴한 회원"으로 보여요'),
                option(true, '동화도 같이 삭제', '되돌릴 수 없어요'),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('취소', style: TextStyle(color: Colors.white54)),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, true),
                style: ElevatedButton.styleFrom(
                    backgroundColor: AdminColors.red, foregroundColor: Colors.white),
                child: const Text('다음'),
              ),
            ],
          );
        },
      ),
    );
    if (step1 != true || !mounted) return;

    final step2 = await adminConfirm(
      context,
      title: '강제 탈퇴 (2/2) 최종 확인',
      message: "정말 '${detail?['nickname']}'(@$userId)님을 탈퇴시킬까요?\n\n"
          "· 게시글 · 댓글 삭제\n"
          "· 동화 $storyCount개 ${deleteStories ? '삭제' : '남김'}\n\n"
          "되돌릴 수 없어요.",
      okText: '탈퇴시키기',
      okColor: AdminColors.red,
    );
    if (!step2) return;

    await _run(() async {
      final response = await ApiClient.delete('$_path?delete_stories=$deleteStories');
      if (!mounted || !adminOk(context, response)) return;
      adminToast(context, '탈퇴 처리했어요.');
      Navigator.pop(context, true);
    });
  }

  // ---------- 화면 ----------
  Widget _section(String title, IconData icon, Widget child) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AdminColors.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AdminColors.purple.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, color: AdminColors.purple, size: 20),
            const SizedBox(width: 8),
            Text(title,
                style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold)),
          ]),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
              width: 80,
              child: Text(label, style: const TextStyle(color: Colors.white54))),
          Expanded(
            child: Text(value.isEmpty ? '-' : value,
                style: const TextStyle(color: Colors.white, fontSize: 15)),
          ),
        ],
      ),
    );
  }

  Widget _count(String label, dynamic value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text('${value ?? 0}',
              style: TextStyle(color: color, fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(color: Colors.white60, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _actionButton(String label, IconData icon, Color color, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: SizedBox(
        width: double.infinity,
        height: 52,
        child: ElevatedButton.icon(
          onPressed: busy ? null : onTap,
          icon: Icon(icon),
          label: Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
          style: ElevatedButton.styleFrom(
            backgroundColor: color,
            foregroundColor: Colors.white,
            disabledBackgroundColor: color.withOpacity(0.4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, changed);
      },
      child: Scaffold(
        backgroundColor: AdminColors.bg,
        appBar: adminAppBar('회원 정보'),
        body: isLoading
            ? adminLoading
            : detail == null
                ? adminEmpty('회원 정보를 찾지 못했어요.')
                : _body(detail!),
      ),
    );
  }

  Widget _body(Map<String, dynamic> d) {
    final bool banned = d['status'] == 'banned';
    final bool isAdmin = d['role'] == 'admin';
    final warnings = (d['warnings'] as List? ?? []).cast<Map<String, dynamic>>();
    final String image = (d['profile_image_url'] ?? '').toString();

    return RefreshIndicator(
      onRefresh: loadDetail,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            CircleAvatar(
              radius: 42,
              backgroundColor: AdminColors.purple,
              backgroundImage: image.isEmpty ? null : NetworkImage(image),
              child: image.isEmpty
                  ? Icon(isAdmin ? Icons.admin_panel_settings : Icons.person,
                      color: Colors.white, size: 42)
                  : null,
            ),
            const SizedBox(height: 12),
            Text(d['nickname'] ?? '',
                style: const TextStyle(
                    color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text('@${d['id']}', style: const TextStyle(color: Colors.white54)),
            const SizedBox(height: 10),
            Wrap(spacing: 6, children: [
              adminTag(banned ? '정지' : '활동', banned ? AdminColors.red : AdminColors.green),
              if (isAdmin) adminTag('관리자', AdminColors.purple),
              adminTag('경고 ${d['warning_count'] ?? 0}회', AdminColors.orange),
            ]),
            const SizedBox(height: 20),
            _section(
              '활동',
              Icons.bar_chart,
              Row(children: [
                _count('만든 동화', d['story_count'], AdminColors.blue),
                _count('게시글', d['post_count'], AdminColors.purple),
                _count('댓글', d['comment_count'], AdminColors.pink),
                _count('받은 신고', d['reports_received'], AdminColors.red),
              ]),
            ),
            _section(
              '기본 정보',
              Icons.person,
              Column(children: [
                _row('이름', (d['name'] ?? '').toString()),
                _row('이메일', (d['email'] ?? '').toString()),
                _row('생년월일', (d['birth'] ?? '').toString()),
                _row('가입 방식', (d['provider'] ?? '').toString().isEmpty ? '일반 가입' : d['provider']),
                _row('가입일', adminDate(d['created_at'])),
                _row('최근 로그인', adminDate(d['last_login'])),
                _row('한 줄 소개', (d['bio'] ?? '').toString()),
              ]),
            ),
            _section(
              '받은 경고 내역 (${warnings.length})',
              Icons.warning_amber,
              warnings.isEmpty
                  ? const Text('받은 경고가 없어요.', style: TextStyle(color: Colors.white54))
                  : Column(
                      children: [
                        for (final w in warnings)
                          Container(
                            width: double.infinity,
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AdminColors.orange.withOpacity(0.08),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(w['reason'] ?? '',
                                    style: const TextStyle(color: Colors.white, height: 1.4)),
                                const SizedBox(height: 4),
                                Text(
                                  '${adminDate(w['created_at'])}'
                                  '${(w['admin_id'] ?? '').toString().isEmpty ? '' : ' · ${w['admin_id']}'}',
                                  style: const TextStyle(color: Colors.white38, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
            ),
            const SizedBox(height: 10),
            _actionButton('경고 주기', Icons.warning, AdminColors.orange, giveWarning),
            if (isAdmin)
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Text('관리자 계정은 정지하거나 탈퇴시킬 수 없어요.',
                    style: TextStyle(color: Colors.white38)),
              )
            else ...[
              _actionButton(
                banned ? '정지 해제' : '이용 정지',
                banned ? Icons.lock_open : Icons.block,
                banned ? AdminColors.green : AdminColors.purple,
                toggleBan,
              ),
              _actionButton('강제 탈퇴', Icons.person_remove, AdminColors.red, forceDelete),
            ],
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}
