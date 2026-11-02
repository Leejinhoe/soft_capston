import 'package:flutter/material.dart';

import '../core/api_client.dart';

class SignUpPage extends StatefulWidget {

  const SignUpPage({super.key});

  @override
  State<SignUpPage> createState() =>
      _SignUpPageState();
}

class _SignUpPageState
    extends State<SignUpPage> {

  final TextEditingController
  idController =
  TextEditingController();

  final TextEditingController
  pwController =
  TextEditingController();

  final TextEditingController
  confirmPwController =
  TextEditingController();

  final TextEditingController
  nameController =
  TextEditingController();

  final TextEditingController
  birthController =
  TextEditingController();

  final TextEditingController
  emailController =
  TextEditingController();

  // 비밀번호 상태
  bool isPasswordValid = false;

  String passwordGuide =
      '영문 대/소문자, 숫자, 특수문자 중 3가지 이상 사용';

  // 아이디 중복 검사 상태
  bool isIdChecked = false;

  bool isIdAvailable = false;

  String idMessage = '';

  // 비밀번호 규칙 검사
  bool validatePassword(
      String password) {

    int count = 0;

    if (RegExp(r'[a-z]')
        .hasMatch(password)) {

      count++;
    }

    if (RegExp(r'[A-Z]')
        .hasMatch(password)) {

      count++;
    }

    if (RegExp(r'[0-9]')
        .hasMatch(password)) {

      count++;
    }

    if (RegExp(
        r'[!@#$%^&*(),.?":{}|<>]')
        .hasMatch(password)) {

      count++;
    }

    return count >= 3;
  }

  // 아이디 중복 검사
  Future<void> checkDuplicateId() async {

    final id =
    idController.text.trim();

    if (id.isEmpty) {

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '아이디를 입력해주세요.',
          ),
        ),
      );

      return;
    }

    try {

      final response = await ApiClient.post(
        '/check-id',
        body: {'id': id},
      );

      final data = ApiClient.decode(response);

      setState(() {

        isIdChecked = true;

        isIdAvailable =
        data['available'];

        if (isIdAvailable) {

          idMessage =
          '사용 가능한 아이디입니다.';

        } else {

          idMessage =
          '이미 사용 중인 아이디입니다.';
        }
      });

    } catch (e) {

      print(e);

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '서버 연결 실패',
          ),
        ),
      );
    }
  }

  Future<void> signUp() async {

    final id =
    idController.text.trim();

    final pw =
    pwController.text.trim();

    final confirmPw =
    confirmPwController.text
        .trim();

    final name =
    nameController.text.trim();

    final birth =
    birthController.text.trim();

    final email =
    emailController.text.trim();

    // 필수 입력 검사
    if (id.isEmpty ||
        pw.isEmpty ||
        confirmPw.isEmpty ||
        name.isEmpty ||
        birth.isEmpty) {

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '필수 항목을 모두 입력해주세요.',
          ),
        ),
      );

      return;
    }

    // 아이디 중복 검사 여부
    if (!isIdAvailable) {

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '아이디 중복검사를 완료해주세요.',
          ),
        ),
      );

      return;
    }

    // 비밀번호 규칙 검사
    if (!validatePassword(pw)) {

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '비밀번호 규칙을 확인해주세요.',
          ),
        ),
      );

      return;
    }

    // 비밀번호 확인
    if (pw != confirmPw) {

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '비밀번호가 일치하지 않습니다.',
          ),
        ),
      );

      return;
    }

    // 이메일 형식 검사
    if (email.isNotEmpty &&
        !email.contains('@')) {

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '올바른 이메일 형식이 아닙니다.',
          ),
        ),
      );

      return;
    }

    // 회원가입 성공
    try {

      final response = await ApiClient.post(
        '/signup',
        body: {
          'id': id,
          'password': pw,
          'name': name,
          'birth': birth,
          'email': email,
        },
      );

      final data = ApiClient.decode(response);

      if (data['success']) {

        ScaffoldMessenger.of(context)
            .showSnackBar(

          const SnackBar(

            content: Text(
              '회원가입 완료',
            ),
          ),
        );

        Navigator.pop(context);

      } else {

        ScaffoldMessenger.of(context)
            .showSnackBar(

          SnackBar(

            content: Text(
              data['message'],
            ),
          ),
        );
      }

    } catch (e) {

      print(e);

      ScaffoldMessenger.of(context)
          .showSnackBar(

        const SnackBar(

          content: Text(
            '서버 연결 실패',
          ),
        ),
      );
    }

  }

  Widget buildTextField({

    required TextEditingController
    controller,

    required String hint,

    required IconData icon,

    bool obscure = false,
  }) {

    return TextField(

      controller: controller,

      obscureText: obscure,

      style: const TextStyle(
        color: Colors.white,
      ),

      decoration: InputDecoration(

        hintText: hint,

        hintStyle:
        const TextStyle(
          color: Colors.white38,
        ),

        prefixIcon: Icon(
          icon,
          color: Colors.white54,
        ),

        filled: true,

        fillColor:
        const Color(0xFF1A0B3A),

        border: OutlineInputBorder(

          borderRadius:
          BorderRadius.circular(18),

          borderSide:
          BorderSide.none,
        ),
      ),
    );
  }

  @override
  void dispose() {

    idController.dispose();

    pwController.dispose();

    confirmPwController.dispose();

    nameController.dispose();

    birthController.dispose();

    emailController.dispose();

    super.dispose();
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor:
      const Color(0xFF070018),

      appBar: AppBar(

        backgroundColor:
        const Color(0xFF070018),

        elevation: 0,

        title: const Text(

          '회원가입',

          style: TextStyle(
            color: Colors.white,
          ),
        ),
      ),

      body: Center(

        child:
        SingleChildScrollView(

          padding:
          const EdgeInsets.all(24),

          child: Container(

            width: 420,

            padding:
            const EdgeInsets.all(32),

            decoration:
            BoxDecoration(

              color:
              const Color(
                0xFF140028,
              ),

              borderRadius:
              BorderRadius.circular(
                32,
              ),

              border: Border.all(
                color:
                Colors.white10,
              ),
            ),

            child: Column(

              children: [

                const Text(

                  '회원가입',

                  style: TextStyle(

                    color:
                    Colors.white,

                    fontSize: 30,

                    fontWeight:
                    FontWeight.bold,
                  ),
                ),

                const SizedBox(
                  height: 30,
                ),

                // 아이디
                Row(

                  children: [

                    Expanded(

                      child:
                      buildTextField(

                        controller:
                        idController,

                        hint: '아이디',

                        icon:
                        Icons.person,
                      ),
                    ),

                    const SizedBox(
                      width: 10,
                    ),

                    ElevatedButton(

                      onPressed:
                      checkDuplicateId,

                      child:
                      const Text(
                        '중복검사',
                      ),
                    ),
                  ],
                ),

                const SizedBox(
                  height: 8,
                ),

                Align(

                  alignment:
                  Alignment.centerLeft,

                  child: Text(

                    idMessage,

                    style: TextStyle(

                      color:
                      isIdAvailable
                          ? Colors.green
                          : Colors.red,

                      fontSize: 12,
                    ),
                  ),
                ),

                const SizedBox(
                  height: 16,
                ),

                // 비밀번호
                TextField(

                  controller:
                  pwController,

                  obscureText: true,

                  style:
                  const TextStyle(
                    color:
                    Colors.white,
                  ),

                  onChanged: (value) {

                    setState(() {

                      isPasswordValid =
                          validatePassword(
                            value,
                          );
                    });
                  },

                  decoration:
                  InputDecoration(

                    hintText:
                    '비밀번호',

                    hintStyle:
                    const TextStyle(
                      color:
                      Colors.white38,
                    ),

                    prefixIcon:
                    const Icon(
                      Icons.lock,
                      color:
                      Colors.white54,
                    ),

                    filled: true,

                    fillColor:
                    const Color(
                      0xFF1A0B3A,
                    ),

                    border:
                    OutlineInputBorder(

                      borderRadius:
                      BorderRadius.circular(
                        18,
                      ),

                      borderSide:
                      BorderSide.none,
                    ),
                  ),
                ),

                const SizedBox(
                  height: 8,
                ),

                Align(

                  alignment:
                  Alignment.centerLeft,

                  child: Text(

                    passwordGuide,

                    style: TextStyle(

                      color:
                      isPasswordValid
                          ? Colors.white70
                          : Colors.grey,

                      fontSize: 12,
                    ),
                  ),
                ),

                const SizedBox(
                  height: 16,
                ),

                buildTextField(

                  controller:
                  confirmPwController,

                  hint:
                  '비밀번호 확인',

                  icon:
                  Icons.lock_outline,

                  obscure: true,
                ),

                const SizedBox(
                  height: 16,
                ),

                buildTextField(

                  controller:
                  nameController,

                  hint: '이름',

                  icon:
                  Icons.badge,
                ),

                const SizedBox(
                  height: 16,
                ),

                buildTextField(

                  controller:
                  birthController,

                  hint:
                  '생년월일 (예: 2000-01-01)',

                  icon:
                  Icons.cake,
                ),

                const SizedBox(
                  height: 16,
                ),

                buildTextField(

                  controller:
                  emailController,

                  hint:
                  '이메일 (선택)',

                  icon:
                  Icons.email,
                ),

                const SizedBox(
                  height: 30,
                ),

                SizedBox(

                  width:
                  double.infinity,

                  height: 60,

                  child:
                  ElevatedButton(

                    onPressed:
                    signUp,

                    style:
                    ElevatedButton.styleFrom(

                      backgroundColor:
                      const Color(
                        0xFF8B5CF6,
                      ),

                      shape:
                      RoundedRectangleBorder(

                        borderRadius:
                        BorderRadius.circular(
                          20,
                        ),
                      ),
                    ),

                    child:
                    const Text(

                      '회원가입',

                      style:
                      TextStyle(

                        color:
                        Colors.white,

                        fontSize: 18,

                        fontWeight:
                        FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}