import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'additional_info_page.dart';
import 'library_page.dart';
import 'login_page.dart';
import 'models/app_state.dart';
import 'notice_page.dart';
import 'psych_page.dart';
import 'services/api_service.dart';
import 'services/db_service.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  Future<void> _showWithdrawalDialog(
    BuildContext context,
    AppState state,
  ) async {
    final accountId = state.currentAccountId?.trim();
    if (accountId == null || accountId.isEmpty) return;

    final isLocal = state.currentProvider == 'local';
    final passwordController = TextEditingController();
    final reasonController = TextEditingController();
    var isSubmitting = false;
    var dialogClosed = false;

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) {
          Future<void> submit() async {
            final password = passwordController.text;
            if (isLocal && password.isEmpty) {
              ScaffoldMessenger.of(
                context,
              ).showSnackBar(const SnackBar(content: Text('비밀번호를 입력해 주세요.')));
              return;
            }

            setDialogState(() => isSubmitting = true);
            try {
              await DbService.withdrawAccount(
                accountId: accountId,
                password: isLocal ? password : null,
                reason: reasonController.text,
              );
              if (!context.mounted) return;
              dialogClosed = true;
              Navigator.pop(dialogContext);
              state.clearSignedInUser();
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (_) => const LoginPage()),
                (_) => false,
              );
              ScaffoldMessenger.of(
                context,
              ).showSnackBar(const SnackBar(content: Text('회원 탈퇴가 완료되었습니다.')));
            } catch (e) {
              if (!context.mounted) return;
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(e.toString().replaceAll('Exception: ', '')),
                ),
              );
            } finally {
              if (context.mounted && !dialogClosed) {
                setDialogState(() => isSubmitting = false);
              }
            }
          }

          return AlertDialog(
            backgroundColor: const Color(0xFF140028),
            title: const Text('회원 탈퇴', style: TextStyle(color: Colors.white)),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '개인정보와 단어장은 삭제되며, 작성한 동화·게시물·댓글은 '
                    '탈퇴한 사용자 이름으로 익명화됩니다. 이 작업은 되돌릴 수 없습니다.',
                    style: TextStyle(color: Colors.white70, height: 1.5),
                  ),
                  if (isLocal) ...[
                    const SizedBox(height: 16),
                    TextField(
                      controller: passwordController,
                      obscureText: true,
                      enabled: !isSubmitting,
                      style: const TextStyle(color: Colors.white),
                      decoration: const InputDecoration(
                        labelText: '현재 비밀번호',
                        labelStyle: TextStyle(color: Colors.white60),
                      ),
                    ),
                  ] else ...[
                    const SizedBox(height: 12),
                    const Text(
                      '소셜 로그인 계정은 비밀번호 확인 없이 탈퇴됩니다.',
                      style: TextStyle(color: Colors.orangeAccent),
                    ),
                  ],
                  const SizedBox(height: 16),
                  TextField(
                    controller: reasonController,
                    enabled: !isSubmitting,
                    maxLength: 500,
                    maxLines: 3,
                    style: const TextStyle(color: Colors.white),
                    decoration: const InputDecoration(
                      labelText: '탈퇴 사유 (선택)',
                      labelStyle: TextStyle(color: Colors.white60),
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed:
                    isSubmitting ? null : () => Navigator.pop(dialogContext),
                child: const Text('취소'),
              ),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.redAccent,
                ),
                onPressed: isSubmitting ? null : submit,
                child: isSubmitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('탈퇴 확인'),
              ),
            ],
          );
        },
      ),
    );

    passwordController.dispose();
    reasonController.dispose();
  }

  Future<void> _showPasswordDialog(BuildContext context, AppState state) async {
    final currentController = TextEditingController();
    final newController = TextEditingController();
    final confirmController = TextEditingController();
    bool isSubmitting = false;
    bool didCloseDialog = false;

    Future<void> submit(
      StateSetter setDialogState,
      BuildContext dialogContext,
    ) async {
      final accountId = state.currentAccountId;
      final currentPassword = currentController.text;
      final newPassword = newController.text;
      final confirmPassword = confirmController.text;

      if (accountId == null || accountId.isEmpty) return;
      if (newPassword.length < 9) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('새 비밀번호는 9자 이상이어야 해요.')));
        return;
      }
      if (newPassword != confirmPassword) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('새 비밀번호 확인이 일치하지 않아요.')));
        return;
      }

      setDialogState(() => isSubmitting = true);
      try {
        await DbService.changePassword(
          accountId: accountId,
          currentPassword: currentPassword,
          newPassword: newPassword,
        );
        if (!context.mounted) return;
        didCloseDialog = true;
        Navigator.pop(dialogContext);
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('비밀번호를 변경했어요.')));
      } catch (e) {
        if (!context.mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '비밀번호 변경 실패: ${e.toString().replaceAll('Exception: ', '')}',
            ),
          ),
        );
      } finally {
        if (context.mounted && !didCloseDialog) {
          setDialogState(() => isSubmitting = false);
        }
      }
    }

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: const Color(0xFF140028),
              title: const Text(
                '비밀번호 변경',
                style: TextStyle(color: Colors.white),
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: currentController,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white),
                    decoration: const InputDecoration(
                      labelText: '현재 비밀번호',
                      labelStyle: TextStyle(color: Colors.white60),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: newController,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white),
                    decoration: const InputDecoration(
                      labelText: '새 비밀번호',
                      helperText: '9자 이상',
                      labelStyle: TextStyle(color: Colors.white60),
                      helperStyle: TextStyle(color: Colors.white38),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: confirmController,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white),
                    decoration: const InputDecoration(
                      labelText: '새 비밀번호 확인',
                      labelStyle: TextStyle(color: Colors.white60),
                    ),
                    onSubmitted: (_) => submit(setDialogState, dialogContext),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed:
                      isSubmitting ? null : () => Navigator.pop(dialogContext),
                  child: const Text('취소'),
                ),
                ElevatedButton(
                  onPressed: isSubmitting
                      ? null
                      : () => submit(setDialogState, dialogContext),
                  child: isSubmitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('변경'),
                ),
              ],
            );
          },
        );
      },
    );

    currentController.dispose();
    newController.dispose();
    confirmController.dispose();
  }

  Widget _infoCard({
    required IconData icon,
    required String title,
    required String value,
    Color color = Colors.purpleAccent,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(icon, color: color, size: 30),
          ),
          const SizedBox(width: 18),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(color: Colors.white54, fontSize: 14),
                ),
                const SizedBox(height: 6),
                Text(
                  value,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _menuButton({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: ListTile(
        onTap: onTap,
        leading: Icon(icon, color: Colors.white),
        title: Text(title, style: const TextStyle(color: Colors.white)),
        trailing: const Icon(
          Icons.arrow_forward_ios,
          color: Colors.white54,
          size: 16,
        ),
      ),
    );
  }

  Widget _statusLine({
    required Future<bool> future,
    required String okText,
    required String badText,
    required IconData icon,
    required Color color,
  }) {
    return FutureBuilder<bool>(
      future: future,
      builder: (context, snapshot) {
        final ok = snapshot.data == true;
        return Row(
          children: [
            Icon(icon, color: ok ? color : Colors.redAccent, size: 18),
            const SizedBox(width: 8),
            Text(
              ok ? okText : badText,
              style: TextStyle(
                color: ok ? color : Colors.redAccent,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final displayName = state.currentDisplayName;
    final totalStories = state.completedStories.length;
    final totalChoices = state.completedStories.fold(
      0,
      (sum, story) => sum + story.allChoicesMade.length,
    );
    final totalWords = state.allVocabulary.length;
    final email = state.currentEmail?.trim();
    final phone = state.currentPhone?.trim();
    final address = state.currentAddress?.trim();
    final providerLabel = switch (state.currentProvider) {
      'google' => 'Google 로그인',
      'kakao' => 'Kakao 로그인',
      'local' => '일반 로그인',
      null || '' => '로그인 정보 없음',
      final other => other,
    };

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(28),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                  ),
                  borderRadius: BorderRadius.circular(32),
                ),
                child: Column(
                  children: [
                    const CircleAvatar(
                      radius: 46,
                      backgroundColor: Colors.white24,
                      child: Icon(Icons.person, size: 52, color: Colors.white),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      '$displayName의 마이페이지',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 30,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      providerLabel,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 30),
              _infoCard(
                icon: Icons.auto_stories,
                title: '생성한 동화',
                value: '$totalStories편',
                color: Colors.purpleAccent,
              ),
              _infoCard(
                icon: Icons.menu_book,
                title: '학습한 단어',
                value: '$totalWords개',
                color: Colors.lightBlueAccent,
              ),
              _infoCard(
                icon: Icons.touch_app,
                title: '선택한 이야기',
                value: '$totalChoices회',
                color: Colors.greenAccent,
              ),
              if (email != null && email.isNotEmpty)
                _infoCard(
                  icon: Icons.email,
                  title: '이메일',
                  value: email,
                  color: Colors.pinkAccent,
                ),
              if (phone != null && phone.isNotEmpty)
                _infoCard(
                  icon: Icons.phone_android,
                  title: '전화번호',
                  value: phone,
                  color: Colors.orangeAccent,
                ),
              if (address != null && address.isNotEmpty)
                _infoCard(
                  icon: Icons.location_on,
                  title: '주소',
                  value: address,
                  color: Colors.tealAccent,
                ),
              Container(
                margin: const EdgeInsets.only(bottom: 28),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: const Color(0xFF140028),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: Colors.white10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '서버 연결',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 14),
                    _statusLine(
                      future: ApiService.checkHealth(),
                      okText: '동화 서버 연결 정상',
                      badText: '동화 서버 연결 확인 필요',
                      icon: Icons.cloud_done,
                      color: Colors.lightBlueAccent,
                    ),
                    const SizedBox(height: 10),
                    _statusLine(
                      future: DbService.checkHealth(),
                      okText: 'DB API 연결 정상',
                      badText: 'DB API 연결 확인 필요',
                      icon: Icons.storage,
                      color: Colors.purpleAccent,
                    ),
                    if (state.isUserDataLoading) ...[
                      const SizedBox(height: 14),
                      const LinearProgressIndicator(
                        color: Colors.purpleAccent,
                        backgroundColor: Colors.white10,
                      ),
                    ],
                    if (state.userDataErrorMessage != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        'DB 기록 동기화 실패: ${state.userDataErrorMessage}',
                        style: const TextStyle(
                          color: Colors.orangeAccent,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const Text(
                '설정',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 20),
              _menuButton(
                icon: Icons.sync,
                title:
                    state.isUserDataLoading ? 'DB 기록 불러오는 중...' : 'DB 기록 새로고침',
                onTap: () async {
                  await context.read<AppState>().loadUserData();
                  if (!context.mounted) return;
                  final error = context.read<AppState>().userDataErrorMessage;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        error == null
                            ? '서재와 단어장을 최신 DB 기록으로 불러왔어요.'
                            : 'DB 기록 새로고침 실패: $error',
                      ),
                    ),
                  );
                },
              ),
              _menuButton(
                icon: Icons.campaign_outlined,
                title: '공지사항',
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const NoticePage()),
                ),
              ),
              if (state.currentAccountId != null &&
                  state.currentAccountId!.isNotEmpty)
                _menuButton(
                  icon: Icons.manage_accounts,
                  title: '프로필 정보 수정',
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => AdditionalInfoPage(
                        accountId: state.currentAccountId!,
                        returnToPrevious: true,
                      ),
                    ),
                  ),
                ),
              if (state.currentProvider == 'local' &&
                  state.currentAccountId != null &&
                  state.currentAccountId!.isNotEmpty)
                _menuButton(
                  icon: Icons.lock_reset,
                  title: '비밀번호 변경',
                  onTap: () => _showPasswordDialog(context, state),
                ),
              _menuButton(
                icon: Icons.library_books,
                title: '내 서재 보기',
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const LibraryPage()),
                ),
              ),
              _menuButton(
                icon: Icons.psychology,
                title: '심리 분석',
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const PsychPage()),
                ),
              ),
              _menuButton(
                icon: Icons.logout,
                title: '로그아웃',
                onTap: () {
                  context.read<AppState>().clearSignedInUser();
                  Navigator.pushAndRemoveUntil(
                    context,
                    MaterialPageRoute(builder: (_) => const LoginPage()),
                    (_) => false,
                  );
                },
              ),
              if (state.currentAccountId != null &&
                  state.currentAccountId!.isNotEmpty)
                _menuButton(
                  icon: Icons.person_off_outlined,
                  title: '회원 탈퇴',
                  onTap: () => _showWithdrawalDialog(context, state),
                ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }
}
