import 'dart:convert';

import 'user_detail_page.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class UserListPage extends StatefulWidget {
  const UserListPage({super.key});

  @override
  State<UserListPage> createState() => _UserListPageState();
}

class _UserListPageState extends State<UserListPage> {

  List users = [];

  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    loadUsers();
  }

  Future<void> loadUsers() async {

    try {

      final response = await http.get(
        Uri.parse("http://127.0.0.1:8000/admin/users"),
      );

      final data = jsonDecode(response.body);

      print(data);

      setState(() {
        users = data;
        isLoading = false;
      });

    } catch (e) {

      print(e);

      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: const Color(0xFF070018),

      appBar: AppBar(

        title: const Text("회원 관리"),

        backgroundColor: const Color(0xFF070018),

        foregroundColor: Colors.white,
      ),

      body: isLoading

          ? const Center(
        child: CircularProgressIndicator(),
      )

          : ListView.builder(

        itemCount: users.length,

        itemBuilder: (context, index) {

          final user = users[index];

          return Card(

            color: const Color(0xFF140028),

            margin: const EdgeInsets.symmetric(
              horizontal: 15,
              vertical: 8,
            ),

            child: ListTile(

              leading: const CircleAvatar(

                backgroundColor: Colors.deepPurple,

                child: Icon(
                  Icons.person,
                  color: Colors.white,
                ),
              ),

              title: Text(

                user["name"] ?? "이름 없음",

                style: const TextStyle(
                  color: Colors.white,
                ),
              ),

              subtitle: Text(

                user["id"] ?? "",

                style: const TextStyle(
                  color: Colors.white70,
                ),
              ),

              trailing: const Icon(
                Icons.arrow_forward_ios,
                color: Colors.white70,
              ),

              onTap: () async {

                final result = await Navigator.push(

                  context,

                  MaterialPageRoute(

                    builder: (_) => UserDetailPage(
                      user: user,
                    ),
                  ),
                );

                if (result == true) {
                  loadUsers();
                }

              },
            ),
          );
        },
      ),
    );
  }
}