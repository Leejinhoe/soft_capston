import 'package:flutter/material.dart';

import '../main.dart';
import '../models/media_readiness.dart';

class MediaReadinessWidget extends StatelessWidget {
  final MediaReadiness? readiness;
  final bool isLoading;
  final String? error;
  final VoidCallback onRefresh;

  const MediaReadinessWidget({
    super.key,
    required this.readiness,
    required this.isLoading,
    required this.error,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.movie_filter_rounded, color: AppColors.teal),
              const SizedBox(width: 10),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '미디어 준비 현황',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      '캐릭터 이미지와 생성 서버 상태',
                      style: TextStyle(color: Colors.white54, fontSize: 12),
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: '현황 새로고침',
                onPressed: isLoading ? null : onRefresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (isLoading && readiness == null)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: CircularProgressIndicator(),
              ),
            )
          else if (error != null && readiness == null)
            _ErrorState(message: error!, onRefresh: onRefresh)
          else if (readiness != null)
            _ReadinessBody(readiness: readiness!),
        ],
      ),
    );
  }
}

class _ReadinessBody extends StatelessWidget {
  final MediaReadiness readiness;

  const _ReadinessBody({required this.readiness});

  @override
  Widget build(BuildContext context) {
    final progress = (readiness.progressPercent / 100).clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              '${readiness.progressPercent}%',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(width: 10),
            Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Text(
                readiness.progressPercent >= 100 ? '준비 완료' : '준비 중',
                style: TextStyle(
                  color: readiness.progressPercent >= 100
                      ? AppColors.teal
                      : AppColors.p300,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 12,
            color: AppColors.teal,
            backgroundColor: Colors.white10,
          ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _MetricChip(
              icon: Icons.person_rounded,
              label:
                  '캐릭터 ${readiness.readyProfiles}/${readiness.targetProfiles}',
            ),
            _MetricChip(
              icon: Icons.image_rounded,
              label: '이미지 ${readiness.readyAssets}/${readiness.targetAssets}',
            ),
            _MetricChip(
              icon: readiness.workerRunning
                  ? Icons.cloud_done_rounded
                  : Icons.cloud_off_rounded,
              label: readiness.workerRunning ? '생성 서버 정상' : '생성 서버 중지',
              color: readiness.workerRunning ? AppColors.teal : AppColors.pink2,
            ),
          ],
        ),
        const SizedBox(height: 16),
        const Divider(color: Colors.white10, height: 1),
        const SizedBox(height: 12),
        ...readiness.characters.map(
          (character) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              children: [
                Icon(
                  character.ready
                      ? Icons.check_circle_rounded
                      : Icons.pending_rounded,
                  size: 18,
                  color: character.ready ? AppColors.teal : AppColors.pink2,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    character.name.isEmpty
                        ? character.characterKey
                        : character.name,
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                Text(
                  '${character.assetCount}/${character.targetAssetCount}장',
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          '생성 작업  대기 ${readiness.queue.pending} · 진행 ${readiness.queue.running} · '
          '완료 ${readiness.queue.completed} · 실패 ${readiness.queue.failed}',
          style: const TextStyle(color: Colors.white54, fontSize: 12),
        ),
      ],
    );
  }
}

class _MetricChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _MetricChip({
    required this.icon,
    required this.label,
    this.color = AppColors.p300,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRefresh;

  const _ErrorState({required this.message, required this.onRefresh});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.error_outline_rounded, color: AppColors.pink2),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            message,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: Colors.white70),
          ),
        ),
        IconButton(
          tooltip: '다시 시도',
          onPressed: onRefresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    );
  }
}
