import 'package:flutter/material.dart';
import '../core/api_client.dart';

class UserDetailPage extends StatelessWidget {
  final Map user;

  const UserDetailPage({
    super.key,
    required this.user,
  });

  Widget infoCard(
      String title,
      String value,
      IconData icon,
      ) {
    return Card(
      color: const Color(0xFF140028),
      margin: const EdgeInsets.only(bottom: 15),
      child: ListTile(
        leading: Icon(
          icon,
          color: Colors.deepPurpleAccent,
        ),
        title: Text(
          title,
          style: const TextStyle(
            color: Colors.white70,
          ),
        ),
        subtitle: Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }

  Future<void> deleteUser(BuildContext context) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text("회원 탈퇴"),
          content: const Text("정말 이 회원을 탈퇴시키겠습니까?"),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(context, false);
              },
              child: const Text("취소"),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context, true);
              },
              child: const Text("확인"),
            ),
          ],
        );
      },
    );

    if (result != true) return;

    try {
      final response = await ApiClient.delete(
        "/admin/user/${Uri.encodeComponent(user["id"].toString())}",
      );

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(response.statusCode == 200
                ? "회원이 삭제되었습니다."
                : ApiClient.errorMessage(response, "회원 삭제 실패")),
          ),
        );

        if (response.statusCode == 200) Navigator.pop(context, true);
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("오류가 발생했습니다.\n$e"),
          ),
        );
      }
    }
  }

  Future<void> warningUser(BuildContext context) async {
    try {
      final response = await ApiClient.put(
        "/admin/warning/${Uri.encodeComponent(user["id"].toString())}",
      );

      final data = ApiClient.decode(response) ?? {};

      if (response.statusCode == 200) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                "경고가 부여되었습니다. (총 ${data["warning_count"]}회)",
              ),
            ),
          );
        }
      } else {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(data["detail"] ?? "경고 부여 실패"),
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("오류가 발생했습니다.\n$e"),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),

      appBar: AppBar(
        title: const Text("회원 정보"),
        backgroundColor: const Color(0xFF070018),
        foregroundColor: Colors.white,
      ),

      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),

        child: Column(
          children: [
            const CircleAvatar(
              radius: 45,
              backgroundColor: Colors.deepPurple,
              child: Icon(
                Icons.person,
                color: Colors.white,
                size: 45,
              ),
            ),

            const SizedBox(height: 20),

            infoCard(
              "이름",
              user["name"] ?? "",
              Icons.person,
            ),

            infoCard(
              "아이디",
              user["id"] ?? "",
              Icons.badge,
            ),

            infoCard(
              "이메일",
              user["email"] ?? "",
              Icons.email,
            ),

            infoCard(
              "생년월일",
              user["birth"] ?? "",
              Icons.cake,
            ),

            infoCard(
              "가입일",
              user["created_at"] ?? "",
              Icons.calendar_month,
            ),

            infoCard(
              "권한",
              user["role"] ?? "user",
              Icons.admin_panel_settings,
            ),

            const SizedBox(height: 30),

            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton.icon(

                onPressed: () {
                  warningUser(context);
                },

                icon: const Icon(Icons.warning),
                label: const Text("경고하기"),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.orange,
                  foregroundColor: Colors.white,
                ),
              ),
            ),

            const SizedBox(height: 15),

            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton.icon(
                onPressed: () {
                  deleteUser(context);
                },
                icon: const Icon(Icons.delete),
                label: const Text("회원 탈퇴"),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}