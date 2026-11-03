# 기능 체크리스트

## 동화 (story)
- [x] `POST /api/generate-story` 동화 생성 + `stories_collection` 자동 저장
- [x] 동화 본문 기반 추천 단어 3~5개 (Gemini + 파이썬 2차 검증)
- [x] 단어 클릭 → 원형 정제 + 문맥 기반 다정한 뜻풀이 팝업
- [ ] 팀원 Colab 동화 서버 연결 (분기 선택지 / 마무리 결말)

## 단어장 (vocabulary)
- [x] `POST /api/vocabularies/add` 단어 저장
- [x] `GET /api/vocabularies/me` 내 단어 목록 (`is_mastered` 포함)
- [x] `DELETE /api/vocabularies/{id}` 내 단어 삭제
- [x] VocabularyPage: 단어 / 출처 동화 제목 / 뜻풀이 (사전 뜻 우선, 비어 있거나 실패 문구면 다정한 뜻풀이)
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
  - 소셜 로그인 계정(`is_social`)은 메뉴 대신 "카카오/네이버/구글에서 관리해요" 안내
- [x] 내가 만든 동화: 목록 / 보기 / 수정(제목·내용) / 삭제
  - `GET /api/users/me/stories`, `GET·PATCH·DELETE /api/stories/{id}` (내 것만, 남의 것은 404)
- [x] 내가 올린 게시글: 목록 / 보기 / 수정 / 삭제
  - `GET /api/users/me/posts`, `GET·PATCH·DELETE /api/posts/{id}` (내 것만)
- [x] 동화 ↔ 게시글 연결 팝업 (아래 커뮤니티 항목과 같은 동작, 목록에 🔗 "연결됨" 표시)
- [x] 스크랩한 글 목록 (`GET /api/users/me/scraps`, 최근 스크랩 순) — `lib/pages/scrap_list_page.dart`
- [x] 받은 좋아요 총합 (`GET /api/users/me/stats` 의 `like_count`)
- [x] 알림함: 공지사항 + 받은 경고(`users.warnings`), 경고가 없으면 공지사항만
  - `GET /api/users/me/inbox`, 공지 등록은 `POST /api/admin/notices` (관리자, 화면은 아직 없음 → `/docs`에서 등록)
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
- [ ] 다음 단계: 게시글 그림(삽화) 표시, 댓글 신고, 관리자 게시글 관리
