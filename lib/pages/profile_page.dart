import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/auth_service.dart';
import '../core/password_rules.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image_cropper/image_cropper.dart';
import '../widgets/custom_bottom_nav.dart';
import 'my_items_page.dart';

const _bg = Color(0xFF070018);
const _card = Color(0xFF140028);

class ProfilePage extends StatefulWidget {
  final String userName;
  final String userEmail;

  const ProfilePage({
    super.key,
    required this.userName,
    this.userEmail = '',
  });

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  late String displayName; // 닉네임
  String realName = ''; // 개인정보: 이름
  late String email;
  String bio = '상상력이 풍부한 동화 탐험가 ✨';
  String? imagePath;
  bool isSocial = false;
  String provider = '';
  bool isLoading = true;

  // 통계 수치 변수
  int storyCount = 0;
  int postCount = 0;
  int likeCount = 0;

  // 공지사항 / 받은 경고
  List<Map<String, dynamic>> notices = [];
  List<Map<String, dynamic>> warnings = [];

  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _fetchProfileData();
    _fetchUserStats();
    _fetchInbox();
  }

  // [GET] 1. 백엔드 DB에서 프로필 정보 불러오기
  Future<void> _fetchProfileData() async {
    try {
      final response = await ApiClient.get('/api/users/me');

      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          displayName = data['nickname'] ?? widget.userName;
          realName = data['real_name'] ?? '';
          email = data['email'] ?? widget.userEmail;
          bio = data['bio'] ?? '상상력이 풍부한 동화 탐험가 ✨';
          imagePath = data['profileImageUrl'];
          isSocial = data['is_social'] == true;
          provider = data['provider'] ?? '';
          isLoading = false;
        });
      } else {
        _setFallbackData();
      }
    } catch (e) {
      debugPrint('프로필 데이터 조회 실패: $e');
      _setFallbackData();
    }
  }

  // [GET] 2. 백엔드 DB에서 통계 정보 불러오기
  Future<void> _fetchUserStats() async {
    try {
      final response = await ApiClient.get('/api/users/me/stats');

      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          storyCount = data['story_count'] ?? 0;
          postCount = data['post_count'] ?? 0;
          likeCount = data['like_count'] ?? 0;
        });
      }
    } catch (e) {
      debugPrint('통계 수치 데이터 조회 실패: $e');
    }
  }

  // [GET] 3. 공지사항 + 내가 받은 경고
  Future<void> _fetchInbox() async {
    try {
      final response = await ApiClient.get('/api/users/me/inbox');
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          notices = (data['notices'] as List? ?? []).cast<Map<String, dynamic>>();
          warnings =
              (data['warnings'] as List? ?? []).cast<Map<String, dynamic>>();
        });
      }
    } catch (e) {
      debugPrint('알림함 조회 실패: $e');
    }
  }

  void _setFallbackData() {
    setState(() {
      displayName = widget.userName.trim().isEmpty ? '사용자' : widget.userName;
      email = widget.userEmail;
      isLoading = false;
    });
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  // [PATCH] 4. 프로필/개인정보 수정 (보낸 항목만 바뀜). 실패하면 안내 문구를 돌려줍니다.
  Future<String?> _updateProfileToApi(Map<String, String> body) async {
    try {
      final response = await ApiClient.patch('/api/users/me', body: body);
      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            displayName = body['nickname'] ?? displayName;
            bio = body['bio'] ?? bio;
            realName = body['name'] ?? realName;
            email = body['email'] ?? email;
          });
        }
        return null;
      }
      return ApiClient.errorMessage(response, '수정하지 못했어요.');
    } catch (e) {
      debugPrint('네트워크 요청 실패: $e');
      return '서버에 연결하지 못했어요.';
    }
  }

  // [PATCH] 5. 비밀번호 변경. 실패하면 안내 문구를 돌려줍니다.
  Future<String?> _changePasswordToApi(
      String currentPassword, String newPassword) async {
    try {
      final response = await ApiClient.patch(
        '/api/users/me/password',
        body: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );
      if (response.statusCode == 200) return null;
      return ApiClient.errorMessage(response, '비밀번호를 바꾸지 못했어요.');
    } catch (e) {
      debugPrint('비밀번호 변경 네트워크 요청 실패: $e');
      return '서버에 연결하지 못했어요.';
    }
  }

  // [POST/MULTIPART] 6. 프로필 이미지 백엔드 업로드
  Future<void> _uploadImageToApi(XFile pickedFile) async {
    try {
      final bytes = await pickedFile.readAsBytes();
      final response = await ApiClient.uploadFile(
        '/api/users/me/image',
        field: 'profile_image',
        bytes: bytes,
        filename: pickedFile.name,
      );

      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          // 이미지 캐시 갱신
          imagePath =
              '${data['imageUrl']}?t=${DateTime.now().millisecondsSinceEpoch}';
        });
        _toast('프로필 사진을 바꿨어요!');
      } else {
        debugPrint('이미지 업로드 실패: ${response.statusCode}');
        _toast('업로드 실패 (${response.statusCode})');
      }
    } catch (e) {
      debugPrint('이미지 업로드 예외 발생: $e');
    }
  }

  // [IMAGE PICK & CROP] 7. 이미지 선택 및 크기 조정
  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? pickedFile = await _picker.pickImage(
        source: source,
        maxWidth: 800,
        maxHeight: 800,
        imageQuality: 85,
      );

      if (pickedFile == null) return;

      // Web 환경에서는 Cropper 동작 실패 방지를 위해 바로 업로드, 앱 환경은 Cropper 적용
      if (kIsWeb) {
        await _uploadImageToApi(pickedFile);
      } else {
        final CroppedFile? croppedFile = await ImageCropper().cropImage(
          sourcePath: pickedFile.path,
          aspectRatio: const CropAspectRatio(ratioX: 1, ratioY: 1),
          compressQuality: 85,
          maxWidth: 500,
          maxHeight: 500,
          uiSettings: [
            AndroidUiSettings(
              toolbarTitle: '프로필 사진 편집',
              toolbarColor: _card,
              toolbarWidgetColor: Colors.white,
              initAspectRatio: CropAspectRatioPreset.square,
              lockAspectRatio: true,
            ),
            IOSUiSettings(
              title: '프로필 사진 편집',
              aspectRatioLockEnabled: true,
            ),
          ],
        );

        if (croppedFile != null) {
          await _uploadImageToApi(XFile(croppedFile.path));
        }
      }
    } catch (e) {
      debugPrint('이미지 선택/편집 오류: $e');
    }
  }

  void _showImagePickerOptions() {
    showModalBottomSheet(
      context: context,
      backgroundColor: _card,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return SafeArea(
          child: Wrap(
            children: [
              ListTile(
                leading:
                    const Icon(Icons.photo_library, color: Colors.purpleAccent),
                title: const Text('갤러리에서 선택',
                    style: TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.pop(context);
                  _pickImage(ImageSource.gallery);
                },
              ),
              if (!kIsWeb)
                ListTile(
                  leading:
                      const Icon(Icons.camera_alt, color: Colors.purpleAccent),
                  title: const Text('카메라로 촬영',
                      style: TextStyle(color: Colors.white)),
                  onTap: () {
                    Navigator.pop(context);
                    _pickImage(ImageSource.camera);
                  },
                ),
            ],
          ),
        );
      },
    );
  }

  // ---------- 공통 다이얼로그 부품 ----------
  InputDecoration _inputDecoration(String label, {String? hint, String? helper}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      helperText: helper,
      helperMaxLines: 2,
      hintStyle: const TextStyle(color: Colors.white24),
      labelStyle: const TextStyle(color: Colors.white70),
      helperStyle: const TextStyle(color: Colors.white54),
      counterStyle: const TextStyle(color: Colors.white38),
      enabledBorder: const UnderlineInputBorder(
        borderSide: BorderSide(color: Colors.white24),
      ),
      focusedBorder: const UnderlineInputBorder(
        borderSide: BorderSide(color: Colors.purpleAccent),
      ),
    );
  }

  /// 입력 다이얼로그 공통 틀. onSave가 안내 문구를 돌려주면 창을 닫지 않고 아래에 보여줍니다.
  void _showFormDialog({
    required String title,
    required List<Widget> Function(StateSetter setDialogState) fields,
    required Future<String?> Function() onSave,
    required String successMessage,
    String saveLabel = '저장',
  }) {
    String? errorText;
    bool isSaving = false;

    showDialog(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (dialogContext, setDialogState) {
            return AlertDialog(
              backgroundColor: _card,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
                side: const BorderSide(color: Colors.white10),
              ),
              title: Text(
                title,
                style: const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.bold),
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ...fields(setDialogState),
                    if (errorText != null) ...[
                      const SizedBox(height: 14),
                      Text(errorText!,
                          style: const TextStyle(color: Colors.redAccent)),
                    ],
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child:
                      const Text('취소', style: TextStyle(color: Colors.white54)),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purpleAccent,
                  ),
                  onPressed: isSaving
                      ? null
                      : () async {
                          setDialogState(() {
                            isSaving = true;
                            errorText = null;
                          });
                          final error = await onSave();
                          if (error == null) {
                            if (dialogContext.mounted) {
                              Navigator.pop(dialogContext);
                            }
                            if (mounted) _toast(successMessage);
                            return;
                          }
                          if (dialogContext.mounted) {
                            setDialogState(() {
                              isSaving = false;
                              errorText = error;
                            });
                          }
                        },
                  child: Text(saveLabel,
                      style: const TextStyle(color: Colors.white)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  // 1. 프로필 수정 다이얼로그 (닉네임, 한 줄 소개)
  void _showEditProfileDialog() {
    final nameController = TextEditingController(text: displayName);
    final bioController = TextEditingController(text: bio);

    _showFormDialog(
      title: '프로필 수정',
      successMessage: '프로필을 수정했어요.',
      fields: (_) => [
        TextField(
          controller: nameController,
          maxLength: 20,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('닉네임'),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: bioController,
          maxLength: 50,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('한 줄 소개'),
        ),
      ],
      onSave: () async {
        final newName = nameController.text.trim();
        if (newName.isEmpty) return '닉네임을 입력해 주세요.';
        return _updateProfileToApi({
          'nickname': newName,
          'bio': bioController.text.trim(),
        });
      },
    );
  }

  // 2. 개인정보 수정 다이얼로그 (이름, 이메일)
  void _showPrivacySettingsDialog() {
    final nameController = TextEditingController(text: realName);
    final emailController = TextEditingController(text: email);

    _showFormDialog(
      title: '개인정보 수정',
      successMessage: '개인정보를 수정했어요.',
      fields: (_) => [
        TextField(
          controller: nameController,
          maxLength: 20,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('이름'),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: emailController,
          keyboardType: TextInputType.emailAddress,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('이메일', hint: 'example@email.com'),
        ),
      ],
      onSave: () async {
        final newName = nameController.text.trim();
        final newEmail = emailController.text.trim();
        if (newName.isEmpty) return '이름을 입력해 주세요.';
        if (newEmail.isNotEmpty &&
            !RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(newEmail)) {
          return '이메일 형식이 올바르지 않아요.';
        }
        return _updateProfileToApi({'name': newName, 'email': newEmail});
      },
    );
  }

  // 3. 비밀번호 변경 다이얼로그 (회원가입과 같은 규칙으로 실시간 검사)
  void _showPasswordChangeDialog() {
    final currentPwController = TextEditingController();
    final newPwController = TextEditingController();
    final confirmPwController = TextEditingController();

    _showFormDialog(
      title: '비밀번호 변경',
      successMessage: '비밀번호를 바꿨어요.',
      saveLabel: '변경',
      fields: (setDialogState) {
        final newPw = newPwController.text;
        final strong = isStrongPassword(newPw);
        return [
          TextField(
            controller: currentPwController,
            obscureText: true,
            style: const TextStyle(color: Colors.white),
            decoration: _inputDecoration('현재 비밀번호'),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: newPwController,
            obscureText: true,
            onChanged: (_) => setDialogState(() {}),
            style: const TextStyle(color: Colors.white),
            decoration: _inputDecoration('새 비밀번호', helper: kPasswordGuide)
                .copyWith(
              helperStyle: TextStyle(
                color: newPw.isEmpty
                    ? Colors.white54
                    : (strong ? Colors.greenAccent : Colors.orangeAccent),
              ),
              suffixIcon: newPw.isEmpty
                  ? null
                  : Icon(strong ? Icons.check_circle : Icons.error_outline,
                      color: strong ? Colors.greenAccent : Colors.orangeAccent),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: confirmPwController,
            obscureText: true,
            onChanged: (_) => setDialogState(() {}),
            style: const TextStyle(color: Colors.white),
            decoration: _inputDecoration('새 비밀번호 확인').copyWith(
              errorText: confirmPwController.text.isNotEmpty &&
                      confirmPwController.text != newPw
                  ? '새 비밀번호와 달라요.'
                  : null,
            ),
          ),
        ];
      },
      onSave: () async {
        final currentPw = currentPwController.text;
        final newPw = newPwController.text;
        final confirmPw = confirmPwController.text;

        if (currentPw.isEmpty || newPw.isEmpty || confirmPw.isEmpty) {
          return '모든 비밀번호 항목을 입력해 주세요.';
        }
        if (!isStrongPassword(newPw)) return '새 비밀번호 규칙을 확인해 주세요.';
        if (newPw != confirmPw) return '새 비밀번호가 서로 달라요.';
        if (newPw == currentPw) return '새 비밀번호가 지금 비밀번호와 같아요.';
        return _changePasswordToApi(currentPw, newPw);
      },
    );
  }

  // 4. 로그아웃 다이얼로그
  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _card,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: const BorderSide(color: Colors.white10),
          ),
          title: const Text(
            '로그아웃',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          content: const Text(
            '정말 로그아웃 하시겠습니까?',
            style: TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('취소', style: TextStyle(color: Colors.white54)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.redAccent,
              ),
              onPressed: () {
                Navigator.pop(context);
                // 토큰 삭제 후 로그인 화면으로
                AuthService.logout();
              },
              child: const Text('로그아웃', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  // 5. 내 동화 / 내 게시글 화면 열기 (수정·삭제가 있었으면 숫자 새로고침)
  Future<void> _openMyItems(MyItemsPage page) async {
    final changed = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => page),
    );
    if (changed == true) _fetchUserStats();
  }

  String get _providerLabel {
    switch (provider) {
      case 'kakao':
        return '카카오';
      case 'naver':
        return '네이버';
      case 'google':
        return '구글';
      default:
        return '소셜';
    }
  }

  // ---------- 화면 부품 ----------
  Widget infoCard({
    required IconData icon,
    required String title,
    required String value,
    VoidCallback? onTap,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 18),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(24),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: Colors.purple.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Icon(icon, color: Colors.purpleAccent, size: 30),
              ),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style:
                          const TextStyle(color: Colors.white54, fontSize: 14),
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
              if (onTap != null)
                const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('보기',
                        style: TextStyle(color: Colors.purpleAccent, fontSize: 13)),
                    Icon(Icons.chevron_right, color: Colors.purpleAccent),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget menuButton({
    required IconData icon,
    required String title,
    String? subtitle,
    VoidCallback? onTap,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: ListTile(
        onTap: onTap,
        leading: Icon(icon, color: onTap == null ? Colors.white38 : Colors.white),
        title: Text(title,
            style: TextStyle(
                color: onTap == null ? Colors.white54 : Colors.white)),
        subtitle: subtitle == null
            ? null
            : Text(subtitle,
                style: const TextStyle(color: Colors.white38, fontSize: 12)),
        trailing: onTap == null
            ? null
            : const Icon(Icons.arrow_forward_ios,
                color: Colors.white54, size: 16),
      ),
    );
  }

  String _date(dynamic iso) {
    final d = DateTime.tryParse((iso ?? '').toString());
    if (d == null) return '';
    return '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';
  }

  Widget _inboxTile({
    required IconData icon,
    required Color color,
    required String title,
    required String body,
    required String date,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(title,
                          style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold)),
                    ),
                    Text(date,
                        style: const TextStyle(
                            color: Colors.white38, fontSize: 12)),
                  ],
                ),
                if (body.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(body,
                      style:
                          const TextStyle(color: Colors.white70, height: 1.5)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Text(
          text,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 24,
            fontWeight: FontWeight.bold,
          ),
        ),
      );

  List<Widget> _buildInbox() {
    return [
      _sectionTitle('알림함'),
      // 경고가 있을 때만 경고 내역을 보여 주고, 없으면 공지사항만 보여 줍니다.
      for (final w in warnings)
        _inboxTile(
          icon: Icons.warning_amber_rounded,
          color: Colors.orangeAccent,
          title: '받은 경고',
          body: (w['reason'] ?? '').toString(),
          date: _date(w['created_at']),
        ),
      for (final n in notices)
        _inboxTile(
          icon: Icons.campaign,
          color: Colors.purpleAccent,
          title: (n['title'] ?? '공지사항').toString(),
          body: (n['content'] ?? '').toString(),
          date: _date(n['created_at']),
        ),
      if (warnings.isEmpty && notices.isEmpty)
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: _card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white10),
          ),
          child: const Text('아직 새로운 공지사항이 없어요.',
              style: TextStyle(color: Colors.white54)),
        ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        backgroundColor: _bg,
        body: Center(
          child: CircularProgressIndicator(color: Colors.purpleAccent),
        ),
      );
    }

    return Scaffold(
      backgroundColor: _bg,
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'profile',
        displayName: displayName,
      ),
      body: SafeArea(
        child: RefreshIndicator(
          color: Colors.purpleAccent,
          onRefresh: () => Future.wait(
              [_fetchProfileData(), _fetchUserStats(), _fetchInbox()]),
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 10),

                // 프로필 상단 카드
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
                      GestureDetector(
                        onTap: _showImagePickerOptions,
                        child: Stack(
                          children: [
                            CircleAvatar(
                              radius: 46,
                              backgroundColor: Colors.white24,
                              backgroundImage: (imagePath != null &&
                                      imagePath!.startsWith('http'))
                                  ? NetworkImage(imagePath!) as ImageProvider
                                  : null,
                              child: (imagePath == null ||
                                      !imagePath!.startsWith('http'))
                                  ? const Icon(
                                      Icons.person,
                                      size: 52,
                                      color: Colors.white,
                                    )
                                  : null,
                            ),
                            Positioned(
                              bottom: 0,
                              right: 0,
                              child: Container(
                                padding: const EdgeInsets.all(6),
                                decoration: const BoxDecoration(
                                  color: Colors.purpleAccent,
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(
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
                        bio,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white70,
                          fontSize: 15,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 30),

                // 통계 카드 (만든 동화 / 작성한 게시글 / 받은 좋아요)
                infoCard(
                  icon: Icons.auto_stories,
                  title: '내가 만든 동화',
                  value: '$storyCount편',
                  onTap: () => _openMyItems(const MyItemsPage.stories()),
                ),
                infoCard(
                  icon: Icons.article,
                  title: '내가 올린 게시글',
                  value: '$postCount개',
                  onTap: () => _openMyItems(const MyItemsPage.posts()),
                ),
                infoCard(
                  icon: Icons.favorite,
                  title: '받은 좋아요',
                  value: '$likeCount개',
                ),

                const SizedBox(height: 20),

                ..._buildInbox(),

                const SizedBox(height: 20),

                _sectionTitle('설정'),

                menuButton(
                  icon: Icons.edit,
                  title: '프로필 수정',
                  subtitle: '닉네임, 한 줄 소개',
                  onTap: _showEditProfileDialog,
                ),

                menuButton(
                  icon: Icons.lock,
                  title: '개인정보 수정',
                  subtitle: '이름, 이메일',
                  onTap: _showPrivacySettingsDialog,
                ),

                // 소셜 로그인 계정은 비밀번호가 없으므로 안내 문구로 대신합니다.
                isSocial
                    ? menuButton(
                        icon: Icons.key_off,
                        title: '비밀번호 변경',
                        subtitle:
                            '$_providerLabel 계정으로 로그인했어요. 비밀번호는 $_providerLabel에서 관리해요.',
                      )
                    : menuButton(
                        icon: Icons.key,
                        title: '비밀번호 변경',
                        onTap: _showPasswordChangeDialog,
                      ),

                menuButton(
                  icon: Icons.logout,
                  title: '로그아웃',
                  onTap: _showLogoutDialog,
                ),

                const SizedBox(height: 100),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
