import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'additional_info_page.dart';
import 'app_theme.dart';
import 'community_page.dart';
import 'library_page.dart';
import 'login_page.dart';
import 'models/app_state.dart';
import 'services/api_service.dart';
import 'services/db_service.dart';
import 'services/profile_image_picker.dart';
import 'social_pages.dart';

String _profileDate(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '');
  if (date == null) return '';
  final local = date.isUtc ? date.toLocal() : date;
  return '${local.year}.${local.month.toString().padLeft(2, '0')}.${local.day.toString().padLeft(2, '0')}';
}

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  late Future<bool> _storyServerHealth;
  late Future<bool> _databaseHealth;
  String? _profileImageUrl;
  String _bio = '';
  int _unreadMessages = 0;
  int _unreadWarnings = 0;
  List<Map<String, dynamic>> _inboxPreview = const [];
  int _myPostCount = 0;
  int _myLikeCount = 0;
  bool _uploadingProfileImage = false;

  @override
  void initState() {
    super.initState();
    _storyServerHealth = ApiService.checkHealth();
    _databaseHealth = DbService.checkHealth();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      unawaited(context.read<AppState>().loadUserData());
      unawaited(_loadSocialProfile());
    });
  }

  Future<void> _loadSocialProfile() async {
    try {
      final accountId = context.read<AppState>().currentAccountId?.trim();
      final values = await Future.wait<dynamic>([
        DbService.fetchMyProfile(),
        DbService.fetchUnreadMessageCount().catchError((_) => 0),
        DbService.fetchMyInbox(
          limit: 100,
        ).catchError((_) => <String, dynamic>{}),
      ]);
      if (!mounted) return;
      final profile = values[0] as Map<String, dynamic>;
      final inbox = values[2] as Map<String, dynamic>;
      setState(() {
        _profileImageUrl = DbService.resolveMediaUrl(
          profile['profile_image_url']?.toString(),
        );
        _bio = profile['bio']?.toString() ?? '';
        _unreadMessages = values[1] as int;
        _unreadWarnings = (inbox['unread_warning_count'] as num?)?.toInt() ?? 0;
        _inboxPreview = (inbox['items'] as List? ?? const [])
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .take(3)
            .toList();
      });
      if (accountId != null && accountId.isNotEmpty) {
        try {
          final publicProfile = await DbService.fetchPublicProfile(accountId);
          if (!mounted) return;
          setState(() {
            _myPostCount =
                (publicProfile['public_post_count'] as num?)?.toInt() ?? 0;
            _myLikeCount = (publicProfile['like_count'] as num?)?.toInt() ?? 0;
          });
        } catch (error) {
          debugPrint('Could not load profile activity counts: $error');
        }
      }
    } catch (error) {
      debugPrint('Could not load social profile summary: $error');
    }
  }

  Future<void> _pickAndUploadProfileImage() async {
    if (_uploadingProfileImage) return;
    try {
      final picked = await pickProfileImage();
      if (picked == null || !mounted) return;
      setState(() => _uploadingProfileImage = true);
      final url = await DbService.uploadProfileImage(
        bytes: picked.bytes,
        filename: picked.filename,
        mimeType: picked.mimeType,
      );
      if (!mounted) return;
      setState(() => _profileImageUrl = url);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('프로필 사진을 저장했어요.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '사진 업로드 실패: ${error.toString().replaceFirst('Exception: ', '')}',
          ),
        ),
      );
    } finally {
      if (mounted && _uploadingProfileImage) {
        setState(() => _uploadingProfileImage = false);
      }
    }
  }

  Future<void> _editProfile(AppState state) async {
    final nicknameController = TextEditingController(
      text: state.currentDisplayName,
    );
    final bioController = TextEditingController(text: _bio);
    final saved = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.pageSurface,
        title: const Text('프로필 편집', style: TextStyle(color: Colors.white)),
        content: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nicknameController,
                maxLength: 80,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(labelText: '닉네임'),
              ),
              TextField(
                controller: bioController,
                maxLength: 300,
                maxLines: 3,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(labelText: '한 줄 소개'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, {
              'nickname': nicknameController.text,
              'bio': bioController.text,
            }),
            child: const Text('저장'),
          ),
        ],
      ),
    );
    nicknameController.dispose();
    bioController.dispose();
    if (saved == null) return;
    try {
      final result = await DbService.updateSocialProfile(
        nickname: saved['nickname']?.toString(),
        bio: saved['bio']?.toString(),
      );
      if (!mounted) return;
      state.updateCurrentNickname(
        result['nickname']?.toString() ?? saved['nickname'].toString(),
      );
      setState(() => _bio = result['bio']?.toString() ?? '');
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('프로필을 수정했어요.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.toString().replaceFirst('Exception: ', '')),
        ),
      );
    }
  }

  void _refreshServerHealth() {
    setState(() {
      _storyServerHealth = ApiService.checkHealth();
      _databaseHealth = DbService.checkHealth();
    });
  }

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
            backgroundColor: AppColors.pageSurface,
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
                onPressed: isSubmitting
                    ? null
                    : () => Navigator.pop(dialogContext),
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
              backgroundColor: AppColors.pageSurface,
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
                  onPressed: isSubmitting
                      ? null
                      : () => Navigator.pop(dialogContext),
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
    VoidCallback? onTap,
    int? badge,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Container(
          margin: const EdgeInsets.only(bottom: 18),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppColors.pageSurface,
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
                      style: const TextStyle(
                        color: Colors.white54,
                        fontSize: 14,
                      ),
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
              if (badge != null && badge > 0)
                Container(
                  margin: const EdgeInsets.only(right: 10),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.pink,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '$badge',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              if (onTap != null)
                const Icon(
                  Icons.arrow_forward_ios_rounded,
                  color: Colors.white38,
                  size: 16,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _recentInboxSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(
              child: Text(
                '알림·공지함',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            if (_unreadWarnings > 0)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Text(
                  '안 읽은 경고 $_unreadWarnings',
                  style: const TextStyle(
                    color: Colors.orangeAccent,
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                  ),
                ),
              ),
            TextButton(
              onPressed: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const InboxPage()),
                );
                if (mounted) unawaited(_loadSocialProfile());
              },
              child: const Text('전체 보기  >'),
            ),
          ],
        ),
        if (_inboxPreview.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.pageSurface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.border),
            ),
            child: const Text(
              '아직 새로운 공지사항이 없어요.',
              style: TextStyle(color: Colors.white54),
            ),
          )
        else
          ..._inboxPreview.map((item) {
            final isWarning = item['type'] == 'warning';
            final unread = isWarning && item['is_read'] != true;
            final color = isWarning ? Colors.orangeAccent : AppColors.p300;
            final body =
                item['body']?.toString() ?? item['content']?.toString() ?? '';
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  borderRadius: BorderRadius.circular(18),
                  onTap: () async {
                    await Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const InboxPage()),
                    );
                    if (mounted) unawaited(_loadSocialProfile());
                  },
                  child: Ink(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: unread
                          ? color.withValues(alpha: 0.09)
                          : AppColors.pageSurface,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: color.withValues(alpha: unread ? 0.6 : 0.22),
                      ),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 36,
                          height: 36,
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.14),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(
                            isWarning
                                ? Icons.warning_amber_rounded
                                : Icons.campaign_rounded,
                            color: color,
                            size: 19,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  if (unread) ...[
                                    Container(
                                      margin: const EdgeInsets.only(right: 6),
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 6,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: AppColors.pink,
                                        borderRadius: BorderRadius.circular(7),
                                      ),
                                      child: const Text(
                                        'NEW',
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontSize: 9,
                                          fontWeight: FontWeight.w900,
                                        ),
                                      ),
                                    ),
                                  ],
                                  Expanded(
                                    child: Text(
                                      item['title']?.toString() ?? '알림',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    _profileDate(item['created_at']),
                                    style: const TextStyle(
                                      color: Colors.white38,
                                      fontSize: 10,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 5),
                              Text(
                                body,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: Colors.white60,
                                  fontSize: 12,
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          }),
      ],
    );
  }

  Widget _menuButton({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
    int? badge,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: Material(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(20),
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          onTap: onTap,
          leading: Icon(icon, color: Colors.white),
          title: Text(title, style: const TextStyle(color: Colors.white)),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (badge != null && badge > 0)
                Container(
                  margin: const EdgeInsets.only(right: 10),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.pinkAccent,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '$badge',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              const Icon(
                Icons.arrow_forward_ios,
                color: Colors.white54,
                size: 16,
              ),
            ],
          ),
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
    final profile = context
        .select<
          AppState,
          ({
            String displayName,
            int totalStories,
            int totalChoices,
            int totalWords,
            String? email,
            String? phone,
            String? address,
            String? provider,
            String? accountId,
            bool isUserDataLoading,
            String? userDataErrorMessage,
          })
        >((state) {
          final stories = state.completedStories;
          return (
            displayName: state.currentDisplayName,
            totalStories: stories.length,
            totalChoices: stories.fold(
              0,
              (sum, story) => sum + story.allChoicesMade.length,
            ),
            totalWords: state.allVocabulary.length,
            email: state.currentEmail?.trim(),
            phone: state.currentPhone?.trim(),
            address: state.currentAddress?.trim(),
            provider: state.currentProvider,
            accountId: state.currentAccountId,
            isUserDataLoading: state.isUserDataLoading,
            userDataErrorMessage: state.userDataErrorMessage,
          );
        });
    final state = context.read<AppState>();
    final displayName = profile.displayName;
    final totalStories = profile.totalStories;
    final totalChoices = profile.totalChoices;
    final totalWords = profile.totalWords;
    final email = profile.email;
    final phone = profile.phone;
    final address = profile.address;
    final noLoadedRecords =
        totalStories == 0 && totalWords == 0 && totalChoices == 0;
    final recordsUnavailable =
        noLoadedRecords &&
        (profile.isUserDataLoading || profile.userDataErrorMessage != null);
    String statValue(int value, String suffix) {
      if (recordsUnavailable && profile.isUserDataLoading) return '불러오는 중';
      if (recordsUnavailable && profile.userDataErrorMessage != null) {
        return '확인 필요';
      }
      return '$value$suffix';
    }

    final providerLabel = switch (profile.provider) {
      'google' => 'Google 로그인',
      'kakao' => 'Kakao 로그인',
      'local' => '일반 로그인',
      null || '' => '로그인 정보 없음',
      final other => other,
    };

    return Scaffold(
      backgroundColor: AppColors.pageBackground,
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
                    InkWell(
                      onTap: _uploadingProfileImage
                          ? null
                          : _pickAndUploadProfileImage,
                      customBorder: const CircleBorder(),
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          CircleAvatar(
                            radius: 46,
                            backgroundColor: Colors.white24,
                            backgroundImage: _profileImageUrl == null
                                ? null
                                : NetworkImage(
                                    _profileImageUrl!,
                                    headers: DbService.mediaHeaders,
                                  ),
                            child: _profileImageUrl == null
                                ? const Icon(
                                    Icons.person,
                                    size: 52,
                                    color: Colors.white,
                                  )
                                : null,
                          ),
                          Positioned(
                            bottom: 0,
                            right: -2,
                            child: Container(
                              padding: const EdgeInsets.all(6),
                              decoration: const BoxDecoration(
                                color: AppColors.p500,
                                shape: BoxShape.circle,
                              ),
                              child: _uploadingProfileImage
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Colors.white,
                                      ),
                                    )
                                  : const Icon(
                                      Icons.camera_alt,
                                      size: 18,
                                      color: Colors.white,
                                    ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      '$displayName의 마이페이지',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 28,
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
                    if (_bio.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(
                        _bio,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white70,
                          height: 1.4,
                        ),
                      ),
                    ],
                    TextButton.icon(
                      onPressed: () => _editProfile(state),
                      icon: const Icon(
                        Icons.edit_outlined,
                        size: 16,
                        color: Colors.white,
                      ),
                      label: const Text(
                        '프로필 수정',
                        style: TextStyle(color: Colors.white),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 30),
              _infoCard(
                icon: Icons.auto_stories,
                title: '내가 만든 동화',
                value: statValue(totalStories, '편'),
                color: AppColors.pink,
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const LibraryPage()),
                ),
              ),
              _infoCard(
                icon: Icons.article_outlined,
                title: '내가 올린 게시글',
                value: '$_myPostCount개',
                color: AppColors.pink2,
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const CommunityPage(initialTab: 2),
                  ),
                ),
              ),
              _infoCard(
                icon: Icons.bookmark_outline,
                title: '스크랩한 글',
                value: '모아 보기',
                color: AppColors.teal,
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const ScrapListPage()),
                ),
              ),
              _infoCard(
                icon: Icons.mail_outline,
                title: '쪽지함',
                value: _unreadMessages > 0 ? '새 쪽지가 왔어요!' : '쪽지 보기',
                color: Colors.lightBlueAccent,
                badge: _unreadMessages,
                onTap: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const MessageBoxPage()),
                  );
                  if (mounted) unawaited(_loadSocialProfile());
                },
              ),
              _infoCard(
                icon: Icons.favorite_outline,
                title: '받은 좋아요',
                value: '$_myLikeCount개',
                color: Colors.pinkAccent,
              ),
              const SizedBox(height: 8),
              _recentInboxSection(),
              const SizedBox(height: 18),
              const SizedBox(height: 6),
              const Text(
                '내 활동 기록',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              _infoCard(
                icon: Icons.menu_book,
                title: '학습한 단어',
                value: statValue(totalWords, '개'),
                color: Colors.lightBlueAccent,
              ),
              _infoCard(
                icon: Icons.touch_app,
                title: '선택한 이야기',
                value: statValue(totalChoices, '회'),
                color: Colors.greenAccent,
              ),
              if (recordsUnavailable && profile.isUserDataLoading)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text(
                    '계정에 저장된 동화와 단어 기록을 확인하고 있어요.',
                    style: TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ),
              if (recordsUnavailable && profile.userDataErrorMessage != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF321B2A),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.orangeAccent),
                    ),
                    child: Text(
                      '기록 조회에 실패해 숫자를 확인할 수 없어요. '
                      '${profile.userDataErrorMessage}',
                      style: const TextStyle(color: Colors.white, fontSize: 14),
                    ),
                  ),
                ),
              if ((email != null && email.isNotEmpty) ||
                  (phone != null && phone.isNotEmpty) ||
                  (address != null && address.isNotEmpty)) ...[
                const SizedBox(height: 6),
                const Text(
                  '계정 정보',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
              ],
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
              const SizedBox(height: 6),
              const Text(
                '서비스 상태',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              Container(
                margin: const EdgeInsets.only(bottom: 28),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.pageSurface,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: Colors.white10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Expanded(
                          child: Text(
                            '서버 연결',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        IconButton(
                          onPressed: _refreshServerHealth,
                          tooltip: '서버 상태 다시 확인',
                          icon: const Icon(Icons.refresh_rounded),
                          color: Colors.white70,
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    _statusLine(
                      future: _storyServerHealth,
                      okText: '동화 서버 연결 정상',
                      badText: '동화 서버 연결 확인 필요',
                      icon: Icons.cloud_done,
                      color: Colors.lightBlueAccent,
                    ),
                    const SizedBox(height: 10),
                    _statusLine(
                      future: _databaseHealth,
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
                icon: Icons.notifications_active_outlined,
                title: '알림·공지함',
                badge: _unreadWarnings,
                onTap: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const InboxPage()),
                  );
                  if (mounted) unawaited(_loadSocialProfile());
                },
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
