import 'package:flutter/material.dart';

import 'main.dart';
import 'models/notice_model.dart';
import 'services/db_service.dart';

class NoticePage extends StatefulWidget {
  const NoticePage({super.key});

  @override
  State<NoticePage> createState() => _NoticePageState();
}

class _NoticePageState extends State<NoticePage> {
  List<Notice> _notices = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final notices = await DbService.fetchNotices();
      if (mounted) {
        setState(() => _notices = notices);
      }
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString().replaceAll('Exception: ', ''));
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.bg,
        surfaceTintColor: Colors.transparent,
        title: const Text('공지사항'),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        color: AppColors.p500,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _ErrorState(message: _error!, onRetry: _load)
                : _notices.isEmpty
                    ? ListView(
                        children: const [
                          SizedBox(height: 170),
                          Icon(Icons.campaign_outlined,
                              size: 52, color: Colors.white38),
                          SizedBox(height: 12),
                          Center(
                            child: Text(
                              '새로운 공지사항이 없습니다.',
                              style: TextStyle(color: Colors.white60),
                            ),
                          ),
                        ],
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.fromLTRB(18, 16, 18, 28),
                        itemCount: _notices.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) => _NoticeCard(
                          notice: _notices[index],
                          onTap: () => _showNotice(_notices[index]),
                        ),
                      ),
      ),
    );
  }

  void _showNotice(Notice notice) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.card,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (context) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 18, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (notice.isPinned)
                    const Padding(
                      padding: EdgeInsets.only(right: 8),
                      child:
                          Icon(Icons.push_pin_rounded, color: AppColors.pink2),
                    ),
                  Expanded(
                    child: Text(
                      notice.title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 21,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close_rounded),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                _formatDate(notice.publishedAt ?? notice.createdAt),
                style: const TextStyle(color: Colors.white54, fontSize: 12),
              ),
              const Divider(height: 30, color: Colors.white12),
              SelectableText(
                notice.content,
                style: const TextStyle(
                    color: Colors.white, height: 1.75, fontSize: 15),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime? value) {
    if (value == null) return '날짜 정보 없음';
    final local = value.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${local.year}.${two(local.month)}.${two(local.day)}';
  }
}

class _NoticeCard extends StatelessWidget {
  final Notice notice;
  final VoidCallback onTap;

  const _NoticeCard({required this.notice, required this.onTap});

  @override
  Widget build(BuildContext context) {
    String date(DateTime? value) {
      if (value == null) return '';
      final local = value.toLocal();
      return '${local.year}.${local.month.toString().padLeft(2, '0')}.${local.day.toString().padLeft(2, '0')}';
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Ink(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
                color: notice.isPinned
                    ? AppColors.pink2.withValues(alpha: 0.5)
                    : Colors.white10),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: (notice.isPinned ? AppColors.pink2 : AppColors.p400)
                      .withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  notice.isPinned
                      ? Icons.push_pin_rounded
                      : Icons.campaign_rounded,
                  color: notice.isPinned ? AppColors.pink2 : AppColors.p300,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      notice.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: Colors.white, fontWeight: FontWeight.w900),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      notice.content,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: Colors.white60, height: 1.4, fontSize: 12),
                    ),
                    const SizedBox(height: 9),
                    Text(date(notice.publishedAt ?? notice.createdAt),
                        style: const TextStyle(
                            color: Colors.white38, fontSize: 11)),
                  ],
                ),
              ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right_rounded, color: Colors.white38),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(30),
      children: [
        const SizedBox(height: 120),
        const Icon(Icons.cloud_off_rounded, color: AppColors.pink2, size: 48),
        const SizedBox(height: 12),
        Text(message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white70)),
        const SizedBox(height: 16),
        Center(
          child: FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('다시 시도'),
          ),
        ),
      ],
    );
  }
}
