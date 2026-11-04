# 📜 Codex 인계 문서: 동화 완성 영상 조립(Story Video Assembly) 및 Cloudflare 화질 복원

- **작성일**: 2026-11-05
- **브랜치**: `codex/media-cleanup` (또는 PR 생성 대상)
- **작업 목적**:
  1. 동화 8개 선택지 진행 중 생성된 미디어(이미지, AI 비디오, 캐릭터 액션)를 동화 종료 시 하나의 완성 동영상(~2.4초/장면, 최대 20초 이내)으로 자연스럽게 결합하는 백엔드/플러터 파이프라인 완성.
  2. Cloudflare Workers AI(`flux-2-klein-4b`)로 생성된 1024×1024 고화질 수채화 일러스트가 기존 영상 조립기에서 360p로 다운스케일링 및 2D 스프라이트로 덮어씌워지던 화질 저하 문제를 해결하고 네이티브 1024×1024 해상도로 복원.

---

## 1. 주요 변경 사항 및 파일별 요약

### 1) 백엔드 영상 조립 엔진 (`backend/story_video_assembly.py`)
- **해상도 확장성 추가**:
  - 기본값은 기존 테스트 호환성을 위해 `width=640, height=360`을 유지하되, 파라미터로 `width=1024, height=1024` (1:1 정사각형 동화책) 또는 `width=1280, height=720` (16:9 와이드 HD) 렌더링을 완전 지원.
  - 1:1 정사각형 모드에서는 양옆 블러 기둥(pillarbox) 없이 1024×1024 Cloudflare 원본 일러스트가 100% 풀프레임으로 렌더링됨.
- **서브픽셀 2.5D Ken Burns 카메라 모션**:
  - `Image.resize(..., resample=LANCZOS, box=(left, top, right, bottom))`을 적용하여 1024p 원본의 선명도를 유지한 채 부드러운 줌인/패닝 구현 (바운딩 박스 클램핑 처리 완료).
- **자연스러운 화면 전환**:
  - 16프레임 코사인 S-커브(Cosine S-curve) 크로스 디졸브 적용. 이전 장면의 잔상 프레임(`tail_frames`)도 멈추지 않고 미세 이동하여 끊김 방지.
- **AI 비디오 클립 프레임 보간**:
  - 12fps 비디오 클립(`Lightricks/LTX-Video`)을 24fps 타겟 프레임에 맞춰 선형 시간 보간(Temporal blending) 및 란초스 스케일링으로 매끄럽게 연결.
- **인공 색감 왜곡 오버레이 제거**:
  - 프레임마다 노란색/뿌연 원을 그리던 `_apply_story_atmosphere`를 기본 비활성화(`enable_atmosphere=False`)하여 Cloudflare 수채화 본연의 맑은 톤 보존.
- **8장면 길이 제약 준수**:
  - 장면당 약 2.4초씩 배정하여 8개 장면 기준 총 19.33초 (464~480프레임 @ 24fps)로 20초 제한 조건 완벽 충족.

### 2) 백엔드 API 라우트 (`backend/main.py`)
- **`POST /api/stories/{story_id}/video/assemble`**:
  - `("video", bytes)`, `("image", bytes)`, `("action", dict)` 하이브리드 입력 처리.
  - **버그 수정**: `use_action_anim` 조건에서 불필요하게 `or prev_kind == "image"`가 들어가 있어 새로 생성된 정상 Cloudflare 이미지를 옛날 2D 스프라이트 시트로 덮어쓰던 버그 제거 (`file_id == prev_file_id`인 중복 장면에서만 액션 모션 적용).
  - 고품질 호출: `assemble_scene_media(items, fps=HIGH_QUALITY_FPS, width=1024, height=1024)`로 Cloudflare 네이티브 해상도 호출.

### 3) 백엔드 단위 테스트 (`backend/test_story_video_assembly.py`)
- 기존 640×360 회귀 테스트 통과 유지.
- 8개 장면 20초 이내 캡핑 테스트, 이미지/비디오/액션 하이브리드 조합 테스트, 미완료 동화 거부 및 미디어 누락 검증 등 총 8개 테스트 통과 (`OK in 17.474s`).

### 4) Flutter 상태 동기화 및 뷰어 (`lib/`)
- **`lib/models/app_state.dart`**:
  - `videoUrl` 정규화 (`/api/media/videos/<24hex>`).
  - `ensureSceneMediaForAssembly`: 동화 종료 시 각 챕터의 미디어가 MongoDB에 온전히 저장되었는지 사전 검증 및 백필(Backfill).
- **`lib/story_page.dart`**:
  - 동화 완료 카드 아래 `_buildJourneyVideo` 위젯 배치.
  - `_makeJourneyVideo` 함수에서 조립 API 호출 및 상태 메시지 실시간 업데이트.
- **`lib/widgets/story_video_player.dart`**:
  - 기존 `aspectRatio: 2` 하드코딩 제거.
  - `aspectRatio` 파라미터 추가 (동화책 1:1 정사각형 기본값 `1.0`, 기존 클립 호환 `2.0` 지원).

---

## 2. 검증 결과 및 산출물

1. **자동화 테스트 검증**:
   - `python -m unittest test_story_video_assembly.py` ➡️ **8/8 통과 (OK)**
   - `flutter analyze lib/models/app_state.dart lib/story_page.dart lib/widgets/story_video_player.dart` ➡️ **No issues found!**
2. **생성된 고화질 결과물**:
   - `artifacts/assembled_male02_cloudflare_1024.mp4` (14.8MB, 1024×1024, 24fps, 19.33초)
   - `artifacts/assembled_male02_cloudflare_720p.mp4` (12.5MB, 1280×720, 24fps, 19.33초)
   - `artifacts/cloudflare_vs_previous_comparison.png` (전후 화질 비교)
   - `artifacts/storyboard_male02_cloudflare_1024.png` (8개 장면 시퀀스 스토리보드)
   - `artifacts/preview_male02_cloudflare_motion.webp` (움직임 프리뷰)

---

## 3. Codex 후속 작업 권장 사항

1. **Flutter 빌드 및 실제 디바이스/웹 테스트**:
   - `flutter run`으로 실제 동화 재생 완료 후 '동화 영상 만들기' 버튼 클릭 시 1:1 풀프레임 영상이 정상 로드되는지 확인.
2. **Hugging Face LTX-Video 해상도 개선 (선택 사항)**:
   - 현재 HuggingFace Space 영상 클립은 384×384로 생성되고 있어, 백엔드에서 란초스로 업스케일링 중입니다. 추후 Space 모델 설정을 512×512 또는 768×768로 올리면 비디오 구간의 화질도 한 단계 더 향상될 수 있습니다.
3. **PR 병합**:
   - `codex/media-cleanup` 브랜치의 변경 사항을 검토 후 `main` 브랜치로 병합하시면 됩니다.
