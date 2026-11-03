# 프로젝트: 어린이 어휘력 향상 AI 동화 앱

5~7세 아이를 위한 분기형 AI 동화 생성 + 동화 속 어휘 학습 웹/앱.
Flutter Web으로 먼저 만들고 같은 코드베이스로 Android 앱 빌드.

## 기술 스택
- Frontend: Flutter (Web 우선, Android 빌드), 다크 테마
- Backend: FastAPI (Python), 비동기(motor) MongoDB
- AI: Gemini API (단어 원형 정제, 뜻풀이, 추천 단어), 국립국어원 표준국어대사전 API
- 팀원 모듈(직접 수정 금지, 래핑해서 사용): 동화 생성, TTS, 그림/영상 생성, 심리분석
    - 위치: `team_code/` (지금은 `team_code/colab/` Colab 노트북), 백엔드에서는 래핑 모듈을 따로 만들어 호출

## 폴더 구조 (실제)
Flutter 프로젝트가 저장소 루트에 있고(`lib/`, `web/`, `android/`, `pubspec.yaml`), 백엔드는 `backend/`에 평평하게 있습니다.
```
lib/                     # Flutter 앱 (http 패키지, shared_preferences)
  main.dart
  core/                  # 공통: api_client(백엔드 주소·토큰·에러 문구), auth_service(로그인/자동 로그인/로그아웃),
                         #       admin_ui(관리자 화면 공통 위젯), password_rules, story_genres, linked_items, banned_notice
  pages/                 # 화면 한 개 = 파일 한 개 (login, signup, password_reset, home, story, vocabulary, quiz,
                         #       board, post_detail, profile, inbox, my_items, scrap_list, message_box, mind,
                         #       admin_page, user_list/detail, report_list/detail, story_admin_list/detail, notice_admin/edit)
  widgets/               # 여러 화면이 같이 쓰는 위젯 (bottom nav, post_card, report_sheet, mini_profile_sheet, message_compose_sheet)
backend/                 # FastAPI (uvicorn main:app), .env도 여기
  main.py                # 앱 생성·라우터 등록·시작 시 인덱스, 동화/단어장/퀴즈/마이페이지/로그인 API
  database.py            # motor 연결, 컬렉션, safe_create_index
  security.py            # JWT, get_current_user / require_admin, 공개 id(public_user_id), 비밀번호 규칙, 정지 안내
  auth.py                # 카카오/네이버/구글 OAuth
  admin.py               # /api/admin/... 요약·회원·동화·공지
  reports.py community.py messages.py quiz.py   # 신고 / 커뮤니티 / 1:1 쪽지 / 퀴즈
  password_reset.py      # 비밀번호 재설정 (인증번호 메일)
  mailer.py              # 메일 발송 공통 (SMTP, HTML 틀)
  gemini_client.py word_meaning.py meaning_cache.py story_text.py   # Gemini·사전·뜻풀이 캐시·본문 정리
  create_admin.py        # 관리자 계정 만들기 스크립트
  static/profile_images/ # 업로드한 프로필 사진
team_code/               # 팀원 코드 원본 (수정 금지)
FEATURES.md              # 페이지별 기능 체크리스트 (진행 상황은 여기에 체크)
```
- 사용자 id: 일반 `id`, 카카오 `kakao_id`, 네이버/구글 `social_id`, 초창기 회원(팀원 스키마)은 `str(_id)`.
  항상 `security.public_user_id` / `find_user_by_public_id` / `public_id_query`로 다룰 것

## 규칙
- **Git: 발표 전까지는 브랜치를 만들지 말고 `master`에 바로 커밋한다.**
- 모든 API는 `/api/...` 접두사, 응답은 Pydantic 스키마로 정의
- 로그인 필요한 API는 JWT 의존성으로 `user_id`를 얻음. 클라이언트가 보낸 user_id를 신뢰하지 말 것
- 관리자 API는 `/api/admin/...` + `require_admin` 의존성
- MongoDB `_id`는 응답 시 문자열 `id`로 변환
- 비밀키/API 키는 `.env`에만. 코드·커밋에 넣지 말 것
- 아이 대상 문구는 다정하고 쉬운 말투
- 기능 하나 끝날 때마다: 백엔드는 `/docs`에서 확인 가능한 상태로, `FEATURES.md` 체크 갱신

## 이미 완성된 것 (건드리기 전에 먼저 읽을 것)
- 단어 클릭 → Gemini로 원형 정제 + 문장 문맥 기반 다정한 뜻풀이 팝업
- `POST /api/vocabularies/add` 단어 저장
- `POST /api/generate-story` 동화 생성, 생성 즉시 `stories_collection`에 자동 저장
- 동화 본문 기반 추천 단어 3~5개 (Gemini + 파이썬 2차 검증)
- `VocabularyPage`: 단어 / 출처 동화 제목 / 다정한 뜻풀이

## 실행 명령
- 백엔드: `cd backend && uvicorn main:app --reload` (가상환경: `backend/venv`)
- 프론트(웹): 저장소 루트에서 `flutter run -d chrome`
- 프론트(안드로이드): 저장소 루트에서 `flutter run`
