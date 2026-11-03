# 기능 체크리스트

## 동화 (story)
- [x] `POST /api/generate-story` 동화 생성 + `stories_collection` 자동 저장
- [x] 동화 본문 기반 추천 단어 3~5개 (Gemini + 파이썬 2차 검증, 뜻은 본문 문장 문맥으로 사전에서 골라 통일 형식)
- [x] 동화 본문 정리: 프롬프트로 마크다운·제목 금지 + 저장 전 `**`, `##`, `*` 등 기호 제거, 첫 줄 제목 빼기 (`backend/story_text.py`)
- [x] 단어 클릭 → 기본형 + 문맥에 맞는 사전 뜻 팝업 (`backend/word_meaning.py`)
  - 기본형 후보를 파이썬으로 만들어(노란→노랗다, 반짝이는→반짝이다, 푹신한→푹신하다) 모두 표준국어대사전에서 조회
  - 동음이의어·다의어의 모든 뜻(`search.do` + `view.do`)을 Gemini에 주고 문맥에 맞는 뜻을 고르게 함 (Gemini 1번)
  - 맞는 뜻이 없으면 Gemini가 직접 씀 (`source`: dictionary / ai / fallback)
  - Gemini 실패 시: 사전 뜻이 1개면 그대로, 여러 개면 "뜻이 여러 가지예요." + 짧은 뜻 2~3개 번호 목록 (`ambiguous: true`)
    - 동음이의어마다 대표 뜻을 먼저 보여줌 (여행 → 여자로서의 행실 / 다른 고장에 가는 일 / 엄격하게 시행함)
    - 이 상태로 저장하면 확정 뜻으로 두지 않음: 저장 때 다시 고르고, 그래도 실패면 `meaning_pending`으로 저장
    - 단어장을 열 때 pending 단어를 한 번에 3개까지 다시 골라 확정 (Gemini가 돌아오면 자동으로 바뀜), 퀴즈에서는 제외
  - 뜻풀이 캐시 (`backend/meaning_cache.py`, 컬렉션 `word_meaning_cache`): 같은 단어 + 같은 문장(+연령대)이면 Gemini 호출 없이 저장된 결과 사용
    - 팝업·단어 저장·pending 재시도·추천 단어 모두 적용, Gemini가 고른 결과만 저장 (예비 결과/"뜻이 여러 가지예요"는 저장 안 함)

## 분기형 동화 (branching) — `backend/branching.py`, `backend/story_engine.py`, `lib/pages/story_page.dart`
- [x] 동화 시작: 주제·장르·연령대 → 첫 장면(2~3문단) + 선택지 3개 `POST /api/stories/branching/start`
- [x] 선택지 고르기 → 고른 선택을 반영한 다음 장면 + 새 선택지 3개 `POST /api/stories/{id}/choose` `{scene_number, choice_index}`
  - `scene_number`가 지금 마지막 장면이 아니면 409 (두 번 눌림·다른 창에서 진행 방지, 화면이 서버 상태로 다시 맞춤)
- [x] "이야기 마무리하기"(첫 장면 이후 아무 때나) → 흐름에 맞는 따뜻한 결말 장면, 선택지 없음 `POST /api/stories/{id}/finish`
- [x] 장면 8개째는 자동으로 결말 (7장면에서 고른 선택을 반영), 6장면부터는 프롬프트로 마무리 쪽으로 유도
- [x] 완료되면 이야기 전체에 어울리는 제목(결말 장면과 같은 Gemini 호출) + 전체 본문 기준 추천 단어 (`backend/story_vocab.py`, 기존 로직 그대로)
- [x] 이어하기/다시 보기 `GET /api/stories/{id}/branching` (예전 통짜 동화는 완료된 장면 1개로 보여줌)
- [x] 저장(`stories`): `scenes[]`(본문·보여준 선택지·고른 선택지), `status`(in_progress/completed), `choice_history[]`(심리분석용), `topic`, `age`
  - `content`는 항상 전체 장면을 이은 본문 → 커뮤니티·관리자·마이페이지 기존 기능 그대로
- [x] 엔진 구조 (`story_engine.py`): Colab 서버(STORY_SERVER_URL 있을 때, 아직 연결 전) → Gemini(장면당 1번, JSON) → AI 없는 예비 장면 순으로 시도
- [x] 화면: 장면이 위에서부터 이어서 보이고, 맨 아래 알록달록 큰 선택지 버튼 3개 + "이야기 마무리하기", 생성 중엔 귀여운 로딩 문구, 모든 장면 단어 클릭 뜻풀이
- [x] 커뮤니티 공유는 완료된 동화만 (서버도 진행 중이면 400), 진행 중인 동화는 본문 수정도 막음
- [x] 마이페이지 "내가 만든 동화": 진행 중이면 "✏️ 만드는 중" 배지 + "이어하기" (`MyItem.status`)
- [ ] 팀원 Colab 동화 서버 연결 (`RemoteStoryEngine` 세 메서드만 채우면 됨)

## 심리분석 (mind) — `backend/psych.py`, `backend/psych_engine.py`, `lib/pages/mind_page.dart`, `lib/pages/mind_detail_page.dart`
- [x] 분석 대상: 완료된 분기형 동화 중 선택을 1번 이상 한 것 (`choice_history`), 진행 중·선택 없이 마무리한 동화·예전 통짜 동화는 제외
- [x] 동화 하나당 Gemini 1번: 5가지 성향 점수 0~100 (용기·도전 `courage`, 배려·공감 `empathy`, 호기심·탐구 `curiosity`, 신중함 `caution`, 창의성 `creativity`)
  + 선택마다 해석 한 줄 + 요약 2~3문장 + 보호자 대화 질문 2개
  - 프롬프트에 장면 내용·보여 준 선택지·고른 것을 같이 줌 ("다른 것 대신 이것을 고른 것"이 근거), 진단·부정적 평가 금지
  - 응답 정리: 점수 0~100으로 자르기(한글 이름·0.7 같은 비율도 받음), 점수가 3개 미만이면 실패, 해석 개수는 선택 수에 맞춰 채움, 질문 2개로 채움
- [x] 결과는 그 동화 문서 `stories.psych_analysis`에 저장 → 다시 볼 때 Gemini 안 부름
  - `{traits, insights[{scene, choice, options, insight}], summary, questions, engine, analyzed_at}`
- [x] `GET /api/psych/me`: 열 때 아직 분석 안 된 완료 동화만 최신순 최대 3개 분석 → 평균(`average`), 최근 5개 변화(`trend`, 오래된 것부터), 동화별 카드(`stories`), 대기 수(`pending_count`)
  - 실패하면 저장하지 않고 그 방문에서는 더 시도 안 함(한도 초과 대비), 다음에 열 때 다시
  - 분석 중 표시(`psych_claimed_at`, 2분)로 동시에 두 번 열어도 같은 동화를 두 번 분석하지 않음
- [x] `GET /api/psych/stories/{id}`: 상세 (아직 분석 전이면 이때 분석, 실패면 503 다정한 문구), 남의 것·진행 중은 404
- [x] 엔진 구조: Colab 서버(STORY_SERVER_URL의 `/story/psych`, 아직 연결 전) → Gemini 순 (`RemotePsychEngine.analyze`만 채우면 됨)
- [x] "놀이 속 선택을 바탕으로 한 참고용 이야기예요" 안내 (응답 `notice`, 목록·상세 모두 표시)
- [x] 화면 (하단 탭 "심리"): 맨 위 평균 성향 레이더 차트 + 점수 칩, 최근 5편 성향 변화 꺾은선(범례 눌러 선 켜고 끄기, 눌러서 점수 보기), 동화별 카드(돋보인 성향 + 요약)
- [x] 상세: 요약, 성향 막대그래프(성향별 고정 색 + 아래 숫자), 선택별 해석(고른 것 + 다른 길), 보호자 대화 질문 2개
- [x] 완료한 동화가 없으면 "동화를 끝까지 만들면 분석해 줄게요!" + "동화 만들러 가기"
- [ ] 팀원 Colab 심리분석 서버 연결 (`RemotePsychEngine`, 요청 형식은 클래스 설명에 적어 둠)

## Gemini 공통
- [x] 한도 초과(429) 시 대체 모델로 자동 재시도 (`backend/gemini_client.py`)
  - `.env`: `GEMINI_FALLBACK_MODELS=모델1,모델2` (쉼표로 구분), 429 난 모델은 10분 동안 건너뜀
  - 동화 생성·추천 단어·뜻풀이 등 모든 Gemini 호출에 적용
- [x] 뜻풀이 형식 통일: 국어사전처럼 간결한 한 문장 (팝업·단어장 저장·추천 단어 공통, 예: "작은 빛이 잠깐 나타났다가 사라지다.")

## 단어장 (vocabulary)
- [x] `POST /api/vocabularies/add` 단어 저장
- [x] `GET /api/vocabularies/me` 내 단어 목록 (`is_mastered` 포함)
- [x] `DELETE /api/vocabularies/{id}` 내 단어 삭제
- [x] VocabularyPage: 단어 / 출처 동화 제목 / 뜻풀이 (문맥에 맞춘 사전식 뜻 `meaning` 우선)
- [x] VocabularyPage: 삭제 버튼(확인 창), 외운 단어 ⭐ 배지, "퀴즈 풀기" 버튼

## 퀴즈 (quiz)
- [x] `GET /api/quiz`: 다정한 뜻풀이 보고 단어 고르기, 4지선다 최대 5문제
  - 안 외운 단어 우선, 외운 단어(`is_mastered`)는 후순위
  - 오답 보기는 다른 저장 단어 → 부족하면 5~7세 기본 단어로 채움
  - 뜻풀이 속 정답 단어는 ○○로 가림
  - 단어가 없으면 `questions: []` + `message: "단어를 먼저 저장해 보세요"`
- [x] `POST /api/quiz/result`: 맞힌 단어 `is_mastered=true`, 푼 단어 `review_count` +1
- [x] QuizPage: 한 문제씩 큰 글씨·큰 버튼, 다정한 정답/오답 피드백, 점수·칭찬, 다시 풀기 / 단어장으로

## 마이페이지 (mypage) — `lib/pages/profile_page.dart`, `lib/pages/my_items_page.dart`
- [x] 프로필 사진 업로드/변경 (기존 `POST /api/users/me/image` 사용, 웹은 갤러리만)
- [x] 프로필 수정: 닉네임, 한 줄 소개 (`PATCH /api/users/me` `nickname`/`bio`)
- [x] 개인정보 수정: 이름, 이메일 (`PATCH /api/users/me` `name`/`email`, 이메일 형식 검사)
- [x] 비밀번호 변경: 현재 비밀번호 확인 + 회원가입과 같은 규칙(영문 대/소문자·숫자·특수문자 중 3가지 이상) 서버/화면 모두 검사
  - 특수문자 = 영문·숫자·공백이 아닌 모든 문자(`~`, `_`, `-` 등). 회원가입·변경·재설정 공통 (`password_rules.dart` / `security.is_strong_password`, 회원가입도 서버에서 검사)
  - 소셜 로그인 계정(`is_social`)은 메뉴 대신 "카카오/네이버/구글에서 관리해요" 안내
- [x] 내가 만든 동화: 목록 / 보기 / 수정(제목·내용) / 삭제
  - `GET /api/users/me/stories`, `GET·PATCH·DELETE /api/stories/{id}` (내 것만, 남의 것은 404)
- [x] 내가 올린 게시글: 목록 / 보기 / 수정 / 삭제
  - `GET /api/users/me/posts`, `GET·PATCH·DELETE /api/posts/{id}` (내 것만)
- [x] 동화 ↔ 게시글 연결 팝업 (아래 커뮤니티 항목과 같은 동작, 목록에 "🌐 커뮤니티에 공유됨"(내 동화) / "📖 내 동화에 있음"(내 게시글) 표시)
- [x] 스크랩한 글 목록 (`GET /api/users/me/scraps`, 최근 스크랩 순) — `lib/pages/scrap_list_page.dart`
- [x] 받은 좋아요 총합 (`GET /api/users/me/stats` 의 `like_count`)
- [x] 알림함: 공지사항 + 받은 경고(`users.warnings`), 경고가 없으면 공지사항만
  - `GET /api/users/me/inbox`: 전체 공지 + 나를 대상으로 한 공지만 (특정 회원 공지는 그 회원에게만)
- [x] 알림함 미리보기: 마이페이지에는 최근 3개만, "전체 보기 >"로 전체 목록 화면(`lib/pages/inbox_page.dart`)
  - 응답 `items`: 안 읽은 경고가 맨 앞, 나머지(읽은 경고 + 공지)는 최신순 / `?limit=3`, `unread_warning_count`
  - 안 읽은 경고는 NEW 배지 + "안 읽은 경고 n", 전체 보기를 열면 `POST /api/users/me/inbox/read`로 읽음(`users.warnings_seen_at`)
- [x] 로그아웃 (기존 유지)

## 커뮤니티 1단계 (community) — `backend/community.py`, `lib/pages/board_page.dart`, `lib/pages/post_detail_page.dart`
- [x] 동화 화면 "커뮤니티에 공유하기" → `POST /api/community/posts` `{story_id}`
  - 게시글은 올린 시점의 복사본, `story_id`로 원본 동화와 연결. 같은 동화를 두 번 올리면 "이미 올린 동화예요"
- [x] 연결 삭제: 게시글 삭제 시 "저장된 동화도 지울까요?", 동화 삭제 시(연결된 글이 있을 때만) "커뮤니티 글도 지울까요?"
  - `DELETE /api/posts/{id}?with_linked=true`, `DELETE /api/stories/{id}?with_linked=true`
  - 게시글이 지워지면 딸린 좋아요/스크랩/댓글도 함께 정리
- [x] 연결 수정: 동화 수정 시(연결된 글이 있을 때만) "커뮤니티 글에도 반영할까요?", 게시글 수정 시 "내 동화에도 반영할까요?"
  - `PATCH ...?sync=true`, 아니요를 골라도 연결은 유지
  - 응답의 `linked_id`: 동화면 연결된 게시글 id, 게시글이면 남아 있는 원본 동화 id (없으면 "")
- [x] 게시글 목록: 최신순, 장르 탭(전체 + 동화 장르 `lib/core/story_genres.dart`), 더보기(10개씩)
  - `GET /api/community/posts?genre=&q=&page=&size=` → `items, total, has_more`
- [x] 검색: 제목 또는 작성자 닉네임 (`q`, 대소문자 무시)
- [x] 상세: 동화 본문, 작성자 프로필 사진·닉네임, 작성일 (`GET /api/community/posts/{id}`)
- [x] 좋아요 토글 (한 사람 1번, `post_likes` 고유 인덱스) `POST /api/community/posts/{id}/like`
- [x] 스크랩 토글 `POST /api/community/posts/{id}/scrap`
- [x] 댓글 작성(300자) / 목록 / 내 댓글 삭제
  - `GET·POST /api/community/posts/{id}/comments`, `DELETE /api/community/comments/{id}` (내 것만)
- [x] 내 글은 상세에서 수정/삭제(연결 팝업 동일), 남의 글은 신고 버튼
- [ ] 다음 단계: 게시글 그림(삽화) 표시

## 커뮤니티 2단계 — 신고 / 미니 프로필 / 1:1 쪽지
### 신고 — `backend/reports.py`, `lib/widgets/report_sheet.dart`
- [x] 게시글·댓글·사용자·쪽지 신고 `POST /api/reports` `{target_type, target_id, reason, detail}`
  - 사유 선택지: 욕설/비방(`abuse`), 부적절한 내용(`inappropriate`), 도배/광고(`spam`), 기타(`other`, 직접 입력 필수, 200자)
- [x] `reports` 컬렉션: `reporter_id, target_type(post/comment/user/message), target_id, target_user_id, post_id(댓글일 때), reason, detail, snapshot{title, content}(신고 당시 내용), status(pending/resolved/rejected), created_at, handled_at, handled_by, admin_memo`
- [x] 같은 사람이 같은 대상 두 번 신고 불가 (고유 인덱스, 409 "이미 신고한 ○○이에요") + 화면에 "신고함" 표시 (`reported`)
- [x] 내 글/내 댓글/나 자신은 신고 버튼 숨김 + 서버에서도 막음, 쪽지는 내가 받은 것만 신고 가능
- [x] 예전 `POST /report`, `GET /admin/reports` 삭제 → 새 구조로 정리, 예전 문서의 `waiting` 상태는 서버 시작 시 `pending`으로 바꿈
- [x] 관리자 API: `GET /api/admin/reports?status=&target_type=&page=&size=`, `GET·PATCH /api/admin/reports/{id}` `{status, admin_memo}`
  - 응답에 신고자/신고당한 회원 닉네임·누적 경고, 원본 남아 있는지(`target_exists`), 같은 대상 신고 수(`same_target_count`) 포함
  - 관리자 신고 관리 화면(`report_list_page.dart`, `report_detail_page.dart`)을 새 구조로 연결: 상태 필터, 경고(공개 id로 정확히), 처리 완료/반려
### 작성자 미니 프로필 — `lib/widgets/mini_profile_sheet.dart`
- [x] 게시글 상세·댓글에서 작성자 이름/사진 누르면 아래에서 올라옴 `GET /api/users/{user_id}/profile`
  - 사진, 닉네임, 한 줄 소개, 공개한 동화 수(커뮤니티 게시글 수), 받은 좋아요 수
- [x] "쪽지 보내기", "신고하기" 버튼 (내 프로필이면 숨김, `is_me`)
### 1:1 쪽지 — `backend/messages.py`, `lib/pages/message_box_page.dart`
- [x] `direct_messages` 컬렉션 (`messages`는 팀원 기능용으로 비워 둠, 인덱스 `dm_receiver_box_idx`·`dm_sender_box_idx`·`dm_receiver_unread_idx`): `sender_id, receiver_id, content(300자), is_read, read_at, reply_to, deleted_by_sender, deleted_by_receiver, created_at`
- [x] `POST /api/messages` 보내기 (자기 자신에게는 불가), `GET /api/messages?box=received|sent`, `GET /api/messages/{id}`(열면 읽음), `GET /api/messages/unread-count`, `DELETE /api/messages/{id}`(내 쪽지함에서만, 양쪽 다 지우면 실제 삭제)
- [x] 마이페이지 "쪽지함": 받은 쪽지 / 보낸 쪽지 탭, 안 읽은 쪽지 배지(마이페이지 카드 + 탭)
- [x] 받은 쪽지: 답장 / 삭제 / 신고, 보낸 쪽지: 읽음 여부 표시, 삭제

## 관리자 (admin) — `backend/admin.py`, `lib/pages/admin_page.dart` 외
모든 API는 `/api/admin/...` + `require_admin`. 화면 공통 스타일은 `lib/core/admin_ui.dart` (다크 + 보라색)
### 관리자 메인 — `admin_page.dart`
- [x] 요약 숫자: 전체 회원 수(관리자 제외), 처리 대기 신고 수, 오늘(한국 시간) 생성된 동화 수 `GET /api/admin/summary`
- [x] 메뉴 4개: 회원 관리 / 신고 관리 / 동화 관리 / 공지사항, 돌아오면 요약 숫자 새로고침
### 회원 관리 — `user_list_page.dart`, `user_detail_page.dart`
- [x] 목록 `GET /api/admin/users?q=&status=active|banned&page=&size=`: 아이디, 닉네임, 이름, 이메일, 가입일, 경고 횟수, 상태(활동/정지), 더보기
  - 검색: 아이디(일반·소셜 id)·닉네임·이름·이메일 (부분 일치, 대소문자 무시)
- [x] 상세 `GET /api/admin/users/{id}`: 기본 정보, 받은 경고 내역(사유·날짜·준 관리자), 만든 동화/게시글/댓글 수, 받은 신고 수
- [x] 경고 주기(사유 필수) `POST /api/admin/users/{id}/warnings` → `users.warnings` + 알림 (마이페이지 알림함에 표시)
  - 신고 상세 화면이 쓰는 `PUT /admin/warning/{id}`도 같은 처리로 유지 (공개 id로만 찾음)
- [x] 정지/정지 해제 `PATCH /api/admin/users/{id}/status` `{status, reason}` (정지되면 다음 요청부터 바로 로그아웃)
  - 정지할 때 사유 필수(`users.ban_reason`, `banned_by`) → 그 회원 이메일로 안내 메일 (아래 "메일")
- [x] 강제 탈퇴 `DELETE /api/admin/users/{id}?delete_stories=&reason=` — 팝업 2번(처리 방법 + 사유 입력 → 최종 확인)
  - 사유 필수, 탈퇴 처리 후 안내 메일 (메일 실패해도 탈퇴는 진행)
  - 게시글(+딸린 좋아요/스크랩/댓글)·댓글·좋아요·스크랩·단어장·알림 삭제, 남의 글 댓글/좋아요 수 보정
  - 동화는 남기기(작성자 "탈퇴한 회원") / 같이 삭제 중 선택, 쪽지는 상대방 쪽지함에만 남김
- [x] 관리자 계정은 정지·탈퇴 불가 (서버 400 + 화면에서 버튼 숨김)
- [x] 정지·탈퇴 팝업에 메일 안내: 이메일이 있으면 "○○로 안내 메일을 보내요", 없으면 "이메일이 없어 안내 메일을 보낼 수 없어요"
  - 응답 `mail`: `queued`(보냄, 결과는 서버 로그) / `no_email` / `not_configured` → 처리 후 토스트에 표시
- [x] 초창기 회원(팀원 스키마 `schema_version`, `account_id`만 있고 `id` 없음)도 상세·경고·정지·탈퇴 가능
  - 원인: 공개 id가 빈 문자열이라 `DELETE /api/admin/users/` → 405
  - 이 회원들의 동화·단어장은 `user_id = str(_id)`로 연결돼 있어서 공개 id도 `str(_id)` (`security.public_user_id`)
  - 화면에는 `login_id`(= `account_id`)를 보여 줌, 검색도 `account_id` 포함, `provider: local`은 일반 가입으로 표시
  - 사용자 찾기는 `security.find_user_by_public_id` / `public_id_query` 한 곳에서 (community·reports·admin 공통)
### 동화 관리 — `story_admin_list_page.dart`, `story_admin_detail_page.dart`
- [x] 모든 회원의 동화 `GET /api/admin/stories?q=&genre=&page=&size=`: 제목, 작성자, 장르, 생성일, 커뮤니티 공유 여부
  - 검색: 제목 또는 작성자(아이디·닉네임·이름), 장르 탭(`kStoryGenres`)
- [x] 상세 `GET /api/admin/stories/{id}` (본문 포함)
- [x] 관리자 삭제 `DELETE /api/admin/stories/{id}?with_linked=` — 공유된 동화면 "연결된 게시글도 지울까요?"
### 공지사항 — `notice_admin_page.dart`, `notice_edit_page.dart`
- [x] 목록 / 등록 / 수정 / 삭제 `GET·POST /api/admin/notices`, `PATCH·DELETE /api/admin/notices/{id}`
- [x] 대상: 전체 회원(`target: all`) / 특정 회원(`target: users`, `user_ids` 여러 명, 아이디 확인 후 추가, 없는 아이디는 400)
  - 예전 공지(대상 필드 없음)는 전체 공지로 취급

## 메일 — `backend/mailer.py`
- [x] 공통 발송 모듈: `.env`의 `SMTP_HOST`, `SMTP_PORT`(465면 SSL, 그 외 STARTTLS), `SMTP_USER`, `SMTP_PASSWORD`
  - 보내는 주소 = 답장 받는 주소(`Reply-To`) = `SMTP_USER`, 제목 앞에 `[AI Fairy Tale]`
  - 앱 이름이 들어간 HTML 틀(`render_mail`) + 텍스트 본문 같이, 사용자/관리자 입력은 모두 이스케이프
  - 발송은 `BackgroundTasks`로 응답 뒤에, 실패해도 예외 없이 서버 로그만 (`[mail:종류] 발송 실패 → ab***@...`)
- [x] 정지·강제 탈퇴 안내 메일: 조치 종류, 사유, 날짜(한국 시간), "이의가 있으면 이 메일에 답장해 주세요"
- [x] 정지된 계정 로그인 안내에 문의 메일 주소(`SMTP_USER`) 표시
  - `/login`: `code: banned`, `contact_email` / 소셜 로그인·요청 중 정지: 403 `detail.contact_email`
  - 로그인 화면은 팝업(`lib/core/banned_notice.dart`)으로 보여 주고 주소를 누르면 복사

## 비밀번호 재설정 — `backend/password_reset.py`, `lib/pages/password_reset_page.dart`
- [x] 로그인 화면 "비밀번호를 잊으셨나요?" → 아이디 + 가입 이메일 → 6자리 인증번호 → 새 비밀번호(+확인) → 로그인 화면
  - `POST /api/auth/password-reset/request` `{id, email}` → 항상 같은 안내 문구 (계정 존재 여부가 드러나지 않음)
  - `POST /api/auth/password-reset/verify` `{id, email, code}` → `reset_token` (10분)
  - `POST /api/auth/password-reset/confirm` `{reset_token, new_password}` (회원가입과 같은 규칙, 화면에서도 확인 칸 검사)
- [x] 인증번호 10분 유효, 5번 틀리면 무효(다시 받아야 함), 재발송은 1분 뒤부터 (화면에 남은 시간/재발송 초 표시)
- [x] 계정이 없거나 이메일이 틀려도 `password_resets` 문서를 똑같이 만들어 확인 단계 응답도 같게 함
  - 아이디·이메일·인증번호·토큰은 원문 없이 `EMAIL_VERIFICATION_PEPPER` HMAC-SHA256으로만 저장, `expires_at` TTL 인덱스로 자동 삭제
  - 같은 이메일로는 (아이디를 바꿔도) 1분에 1통만 발송
- [x] 소셜 계정: 화면에 "카카오/네이버/구글에서 관리해요" 안내 + 그 이메일로 안내 메일(인증번호 없음)
- [x] 정지 계정: 재설정 불가 (인증번호 대신 문의 주소 안내 메일, 확인·변경 단계에서도 다시 막음)
- [ ] 초창기 회원(`account_id`)은 지금 로그인 자체가 `id` 기준이라 재설정 대상에서 빠짐 (로그인 지원 시 같이 추가)
