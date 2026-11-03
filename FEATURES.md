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
