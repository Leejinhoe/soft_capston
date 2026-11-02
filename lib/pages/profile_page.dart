import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/auth_service.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image_cropper/image_cropper.dart';
import '../widgets/custom_bottom_nav.dart';

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
  late String displayName;
  late String email;
  String bio = '상상력이 풍부한 동화 탐험가 ✨';
  String? imagePath;
  bool isLoading = true;

  // 통계 수치 변수
  int storyCount = 0;
  int postCount = 0;
  int likeCount = 0;

  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _fetchProfileData();
    _fetchUserStats();
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
          email = data['email'] ?? widget.userEmail;
          bio = data['bio'] ?? '상상력이 풍부한 동화 탐험가 ✨';
          imagePath = data['profileImageUrl'];
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

  void _setFallbackData() {
    setState(() {
      displayName = widget.userName.trim().isEmpty ? '사용자' : widget.userName;
      email = widget.userEmail;
      isLoading = false;
    });
  }

  // [PATCH/PUT] 3. 백엔드 REST API로 프로필 수정 전송
  Future<bool> _updateProfileToApi(
      String newName, String newEmail, String newBio) async {
    try {
      final response = await ApiClient.patch(
        '/api/users/me',
        body: {
          'nickname': newName,
          'email': newEmail,
          'bio': newBio,
        },
      );

      if (response.statusCode == 200) {
        setState(() {
          displayName = newName;
          email = newEmail;
          bio = newBio;
        });
        return true;
      } else {
        debugPrint('서버 응답 오류: ${response.statusCode}');
        return false;
      }
    } catch (e) {
      debugPrint('네트워크 요청 실패: $e');
      return false;
    }
  }

  // [PATCH/PUT] 4. 백엔드 REST API로 비밀번호 변경 전송
  Future<Map<String, dynamic>> _changePasswordToApi(
      String currentPassword, String newPassword) async {
    try {
      final response = await ApiClient.patch(
        '/api/users/me/password',
        body: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );

      if (response.statusCode == 200) {
        return {'success': true, 'message': '비밀번호가 성공적으로 변경되었습니다.'};
      } else {
        return {
          'success': false,
          'message': ApiClient.errorMessage(response, '비밀번호 변경 실패 (서버 에러)')
        };
      }
    } catch (e) {
      debugPrint('비밀번호 변경 네트워크 요청 실패: $e');
      return {'success': false, 'message': '서버 연결 실패 (네트워크 확인)'};
    }
  }

  // [POST/MULTIPART] 5. 프로필 이미지 백엔드 업로드
  Future<void> _uploadImageToApi(XFile pickedFile) async {
    try {
      final bytes = await pickedFile.readAsBytes();
      final response = await ApiClient.uploadFile(
        '/api/users/me/image',
        field: 'profile_image',
        bytes: bytes,
        filename: pickedFile.name,
      );

      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          // 이미지 캐시 갱신
          imagePath = '${data['imageUrl']}?t=${DateTime.now().millisecondsSinceEpoch}';
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('프로필 이미지가 변경되었습니다!')),
          );
        }
      } else {
        debugPrint('이미지 업로드 실패: ${response.statusCode}');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('업로드 실패 (${response.statusCode})')),
          );
        }
      }
    } catch (e) {
      debugPrint('이미지 업로드 예외 발생: $e');
    }
  }

  // [IMAGE PICK & CROP] 6. 이미지 선택 및 크기 조정
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
              toolbarColor: const Color(0xFF140028),
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
      backgroundColor: const Color(0xFF140028),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return SafeArea(
          child: Wrap(
            children: [
              ListTile(
                leading: const Icon(Icons.photo_library, color: Colors.purpleAccent),
                title: const Text('갤러리에서 선택', style: TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.pop(context);
                  _pickImage(ImageSource.gallery);
                },
              ),
              ListTile(
                leading: const Icon(Icons.camera_alt, color: Colors.purpleAccent),
                title: const Text('카메라로 촬영', style: TextStyle(color: Colors.white)),
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

  // 1. 프로필 수정 다이얼로그 (닉네임, 한 줄 소개)
  void _showEditProfileDialog() {
    final nameController = TextEditingController(text: displayName);
    final bioController = TextEditingController(text: bio);

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF140028),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: const BorderSide(color: Colors.white10),
          ),
          title: const Text(
            '프로필 수정',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameController,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(
                  labelText: '닉네임',
                  labelStyle: TextStyle(color: Colors.white70),
                  enabledBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.white24),
                  ),
                  focusedBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.purpleAccent),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: bioController,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(
                  labelText: '한 줄 소개',
                  labelStyle: TextStyle(color: Colors.white70),
                  enabledBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.white24),
                  ),
                  focusedBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.purpleAccent),
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('취소', style: TextStyle(color: Colors.white54)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.purpleAccent,
              ),
              onPressed: () async {
                final newName = nameController.text.trim().isEmpty
                    ? '사용자'
                    : nameController.text.trim();
                final newBio = bioController.text.trim();

                bool success = await _updateProfileToApi(newName, email, newBio);

                if (mounted) {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        success
                            ? '프로필이 성공적으로 수정되었습니다.'
                            : '서버 수정 실패 (네트워크 확인)',
                      ),
                    ),
                  );
                }
              },
              child: const Text('저장', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  // 2. 개인정보 설정 다이얼로그 (이메일 및 닉네임)
  void _showPrivacySettingsDialog() {
    final emailController = TextEditingController(text: email);
    final nameController = TextEditingController(text: displayName);

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF140028),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: const BorderSide(color: Colors.white10),
          ),
          title: const Text(
            '개인정보 설정 및 수정',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: emailController,
                  style: const TextStyle(color: Colors.white),
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: '가입 계정 (이메일)',
                    hintText: '이메일을 입력하세요',
                    hintStyle: TextStyle(color: Colors.white24),
                    labelStyle: TextStyle(color: Colors.white70),
                    enabledBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.white24),
                    ),
                    focusedBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.purpleAccent),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: nameController,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    labelText: '가입한 이름/닉네임',
                    labelStyle: TextStyle(color: Colors.white70),
                    enabledBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.white24),
                    ),
                    focusedBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.purpleAccent),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('취소', style: TextStyle(color: Colors.white54)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.purpleAccent,
              ),
              onPressed: () async {
                final newEmail = emailController.text.trim();
                final newName = nameController.text.trim().isEmpty
                    ? '사용자'
                    : nameController.text.trim();

                bool success = await _updateProfileToApi(newName, newEmail, bio);

                if (mounted) {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        success ? '개인정보가 수정되었습니다.' : '서버 수정 실패',
                      ),
                    ),
                  );
                }
              },
              child: const Text('저장', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  // 3. 비밀번호 변경 다이얼로그
  void _showPasswordChangeDialog() {
    final currentPwController = TextEditingController();
    final newPwController = TextEditingController();
    final confirmPwController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF140028),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: const BorderSide(color: Colors.white10),
          ),
          title: const Text(
            '비밀번호 변경',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: currentPwController,
                  obscureText: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    labelText: '현재 비밀번호',
                    labelStyle: TextStyle(color: Colors.white70),
                    enabledBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.white24),
                    ),
                    focusedBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.purpleAccent),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: newPwController,
                  obscureText: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    labelText: '새 비밀번호',
                    labelStyle: TextStyle(color: Colors.white70),
                    enabledBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.white24),
                    ),
                    focusedBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.purpleAccent),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: confirmPwController,
                  obscureText: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    labelText: '새 비밀번호 확인',
                    labelStyle: TextStyle(color: Colors.white70),
                    enabledBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.white24),
                    ),
                    focusedBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: Colors.purpleAccent),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('취소', style: TextStyle(color: Colors.white54)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.purpleAccent,
              ),
              onPressed: () async {
                final currentPw = currentPwController.text.trim();
                final newPw = newPwController.text.trim();
                final confirmPw = confirmPwController.text.trim();

                if (currentPw.isEmpty || newPw.isEmpty || confirmPw.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('모든 비밀번호 항목을 입력해주세요.')),
                  );
                  return;
                }

                if (newPw != confirmPw) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('새 비밀번호가 서로 일치하지 않습니다.')),
                  );
                  return;
                }

                final result = await _changePasswordToApi(currentPw, newPw);

                if (mounted) {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(result['message'])),
                  );
                }
              },
              child: const Text('변경', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  // 4. 로그아웃 다이얼로그
  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF140028),
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

  Widget infoCard({
    required IconData icon,
    required String title,
    required String value,
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
              color: Colors.purple.withOpacity(0.2),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(
              icon,
              color: Colors.purpleAccent,
              size: 30,
            ),
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

  Widget menuButton({
    required IconData icon,
    required String title,
    VoidCallback? onTap,
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

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        backgroundColor: Color(0xFF070018),
        body: Center(
          child: CircularProgressIndicator(color: Colors.purpleAccent),
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'profile',
        displayName: displayName,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
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
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      bio,
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
                title: '생성한 동화',
                value: '$storyCount편',
              ),
              infoCard(
                icon: Icons.article,
                title: '작성한 게시글',
                value: '$postCount개',
              ),
              infoCard(
                icon: Icons.favorite,
                title: '받은 좋아요',
                value: '$likeCount개',
              ),

              const SizedBox(height: 20),

              const Text(
                '설정',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),

              const SizedBox(height: 20),

              menuButton(
                icon: Icons.edit,
                title: '프로필 수정',
                onTap: _showEditProfileDialog,
              ),

              menuButton(
                icon: Icons.lock,
                title: '개인정보 설정',
                onTap: _showPrivacySettingsDialog,
              ),

              menuButton(
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
    );
  }
}