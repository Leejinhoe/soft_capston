# 프로젝트: 어린이 어휘력 향상 AI 동화 앱

5~7세 아이를 위한 분기형 AI 동화 생성 + 동화 속 어휘 학습 웹/앱.
Flutter Web으로 먼저 만들고 같은 코드베이스로 Android 앱 빌드.

## 기술 스택
- Frontend: Flutter (Web 우선, Android 빌드), 다크 테마
- Backend: FastAPI (Python), 비동기(motor) MongoDB
- AI: Gemini API (단어 원형 정제, 뜻풀이, 추천 단어), 국립국어원 표준국어대사전 API
- 팀원 모듈(직접 수정 금지, 래핑해서 사용): 동화 생성, TTS, 그림/영상 생성, 심리분석
    - 위치: `backend/external/` 아래 각 모듈, 호출은 `backend/app/services/`의 어댑터를 통해서만

## 폴더 구조 (목표)
```
frontend/lib/
  core/        # 테마, 라우터, API 클라이언트(dio), 인증 토큰 저장
  models/      # API 응답 모델
  features/<기능>/  # auth, home, story, community, vocabulary, analysis, mypage, admin
     pages/ widgets/ providers/
backend/app/
  main.py
  core/        # 설정(.env), DB 연결, JWT/보안, 권한(get_current_user, require_admin)
  models/      # Pydantic 스키마
  routers/     # auth, users, stories, vocabularies, quiz, community, messages, reports, admin, notices, analysis
  services/    # 비즈니스 로직 + 외부 AI 어댑터
backend/external/  # 팀원 코드 원본
docs/FEATURES.md   # 페이지별 기능 체크리스트 (진행 상황은 여기에 체크)
```

## 규칙
- **Git: 발표 전까지는 브랜치를 만들지 말고 `master`에 바로 커밋한다.**
- 모든 API는 `/api/...` 접두사, 응답은 Pydantic 스키마로 정의
- 로그인 필요한 API는 JWT 의존성으로 `user_id`를 얻음. 클라이언트가 보낸 user_id를 신뢰하지 말 것
- 관리자 API는 `/api/admin/...` + `require_admin` 의존성
- MongoDB `_id`는 응답 시 문자열 `id`로 변환
- 비밀키/API 키는 `.env`에만. 코드·커밋에 넣지 말 것
- 아이 대상 문구는 다정하고 쉬운 말투
- 기능 하나 끝날 때마다: 백엔드는 `/docs`에서 확인 가능한 상태로, `docs/FEATURES.md` 체크 갱신

## 이미 완성된 것 (건드리기 전에 먼저 읽을 것)
- 단어 클릭 → Gemini로 원형 정제 + 문장 문맥 기반 다정한 뜻풀이 팝업
- `POST /api/vocabularies/add` 단어 저장
- `POST /api/generate-story` 동화 생성, 생성 즉시 `stories_collection`에 자동 저장
- 동화 본문 기반 추천 단어 3~5개 (Gemini + 파이썬 2차 검증)
- `VocabularyPage`: 단어 / 출처 동화 제목 / 다정한 뜻풀이

## 실행 명령
- 백엔드: `cd backend && uvicorn app.main:app --reload`
- 프론트(웹): `cd frontend && flutter run -d chrome`
- 프론트(안드로이드): `cd frontend && flutter run`
