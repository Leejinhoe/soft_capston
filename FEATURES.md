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
- [x] 엔진 구조 (`story_engine.py`): 팀원 Colab 서버(STORY_SERVER_URL) → Gemini(장면당 1번, JSON) → AI 없는 예비 장면 순으로 시도
- [x] 화면: 장면이 위에서부터 이어서 보이고, 맨 아래 알록달록 큰 선택지 버튼 3개 + "이야기 마무리하기", 생성 중엔 귀여운 로딩 문구, 모든 장면 단어 클릭 뜻풀이
- [x] 커뮤니티 공유는 완료된 동화만 (서버도 진행 중이면 400), 진행 중인 동화는 본문 수정도 막음
- [x] 마이페이지 "내가 만든 동화": 진행 중이면 "✏️ 만드는 중" 배지 + "이어하기" (`MyItem.status`)
- [x] 팀원 Colab 동화 서버 연결 (`RemoteStoryEngine`, 공통 호출 `backend/colab_client.py`)
  - 첫 장면 `POST /story/start`, 다음 장면 `POST /story/continue`, Colab story_id는 `stories.colab_story_id`
  - 마무리/8장면 결말: "모두 함께 행복하게 이야기를 마무리한다" 선택지를 보내고 돌아온 선택지는 버림, 제목은 Gemini(20초) → 안 되면 주제로
  - 기존 후처리 + 보이지 않는 문자·겹친 문장부호 정리 (`clean_colab_text`), 타임아웃 120초
  - 고른 선택지의 KOTE 감정(`selected_choice_emotion` 요약)을 `choice_history[].emotion`에 저장 (심리분석용)
  - Colab이 꺼지거나(연결 실패 → 60초 동안 건너뜀) 느리거나 실패하면 Gemini → 예비 장면
- [x] 시연 중 Colab이 꺼져도 멈추지 않게 (`colab_client.FIRST_EVENT_TIMEOUT_SEC`)
  - 주소가 죽었으면 바로, 터널은 살아 있는데 Colab이 답을 안 하면 15초 만에 Gemini로 (그 뒤 60초 동안 Colab 건너뜀)
  - 우리 서버가 보낸 다른 Colab 요청(그림·TTS 등)이 처리 중일 땐 그게 끝날 때까지 기다려 줌 (Colab이 한 번에 하나만 처리해서)
- [x] Gemini가 느려도 멈추지 않게 (`gemini_client.FallbackModel`)
  - 장면 하나 45초 제한 (넘으면 예비 장면), 모델 하나 40초 제한, 504·503·500이면 다음 모델 (1분만 건너뜀)
  - 첫 모델이 8초 안에 답이 없으면 다음 모델에도 같이 보내서 먼저 온 답 사용 (동시에 2개까지, 무료 한도 아끼기)
  - 추천 단어 25초, 단어 뜻풀이 20초, 기본 목소리(gTTS) 15초 제한 → 넘으면 각자 예비 동작
  - 주소가 바뀌면 `.env`의 STORY_SERVER_URL만 고치고 백엔드 재시작
- [x] 장면을 만든 엔진을 장면 카드에 작게 표시 ("🤖 우리 팀 AI" / "✨ Gemini" / "📘 기본 이야기", `SceneOut.engine`)
- [x] 동화 생성은 우리 팀이 학습시킨 Colab 모델이 주인공 (Gemini는 Colab이 꺼지거나 실패할 때만)
- [x] 스트리밍: 장면 글이 만들어지는 대로 화면에 한 글자씩 (`POST .../start/stream`, `.../{id}/choose/stream`, `.../{id}/finish/stream`)
  - Colab `/story/start/stream`, `/story/continue/stream`(NDJSON meta·delta·status·complete·error)을 받아 우리 서버도 NDJSON으로 전달
    (`engine` / `text`(정리한 지금까지 본문) / `status` / `reset` / `state`(DB 저장 후 최종 상태) / `error`)
  - Colab 스트리밍이 실패하면 Colab 일반 호출 → Gemini → 예비 장면, 화면은 스트리밍 연결이 안 되면 일반 API로
  - 만들기는 별도 작업이라 화면이 중간에 끊겨도 끝까지 저장 (화면은 저장될 때까지 기다렸다가 불러옴)
  - 잘못된 요청(끝난 동화, 빈 주제 등)은 스트리밍 시작 전에 보통 HTTP 오류
  - 웹은 기본 http가 스트리밍을 못 해서 `fetch_client` (`lib/core/stream_client*.dart`, 조건부 import)
- [x] 생성 중 문구: 엔진마다 다른 다정한 문구를 돌아가며 ("✍️ 이야기 요정이 한 글자 한 글자 동화를 적고 있어요" / "🌟 곧 동화가 완성돼요…"), 쓰는 중인 장면 카드 + 선택지 준비 안내
- [x] 엔진 전환은 화면에 드러내지 않음 (서버 로그에만): "Gemini", "대신", "쉬어서" 같은 말 없음
  - 장면 카드 표시는 우리 팀 AI 장면에만 "🤖 우리 팀 AI", Gemini·기본 이야기 장면은 표시 없음
  - 목소리·심리분석·동화 실패 문구도 기술 용어 없이 ("이번에는 기본 목소리로 읽어 줄게요 🎧")
- [x] 선택지가 Colab 기본값("계속 나아간다 / 도움을 요청한다 / 잠깐 생각해본다")이면 Colab `/story/choices`로 다시 → 그래도 기본값이면 그때만 Gemini로 선택지만
  - JSON·코드 찌꺼기 선택지(실제로 `javascript`, `description": "…` 가 온 적 있음)도 다시 만들기
- [x] 선택지가 장면마다 똑같던 문제: Colab·/story/choices·Gemini가 다 실패하면 Colab 기본값이 매번 나가던 것 (`backend/story_choices.py`)
  - 어느 엔진이든 마지막에: 이번 장면에 맞고, 이 동화의 이전 선택지와 겹치지 않는 3개 (`finalize_choices`, Gemini 프롬프트에도 이전 선택지 전달)
  - 모자라면 장면 본문의 등장인물·장소·물건 낱말로 템플릿 선택지 ("다람쥐에게 도와 달라고 말해 본다", "연못에서 숨은 친구를 찾아본다")
  - 무서운 등장인물(악마·마녀 등)은 템플릿에 쓰지 않음, 서버 로그 `[선택지] …`
- [x] Colab 본문의 HTML 찌꺼기 정리 (`</br>` → 줄바꿈, `<p>` `<strong>` `[ ]` 지움, 스트리밍 중 덜 온 태그는 숨김)
- [x] 조사 앞 띄어쓰기 고치기 (`story_text.fix_particle_spacing`, Colab 본문에만): "토끼 는" → "토끼는", "뿔 을" → "뿔을"
  - 보수적으로: 조사가 떨어진 낱말일 때만, 앞 낱말이 어미·조사로 끝나거나 부사·관형사면 그대로, 받침과 조사가 맞을 때만
  - 테스트 문장 36개(고칠 것 19 + 그대로 둘 것 17) 확인
- [x] 장면 그림 (`backend/story_images.py`): 본문이 먼저 나오고 화면이 따로 `POST /api/stories/{id}/scenes/{n}/colab-image` → Colab `/story/image`
  - 주소가 `/image`가 아닌 이유: `/image`는 팀원 캐릭터 그림(아래)이 씀. `SceneOut.image_url`은 캐릭터 그림이 있으면 그걸 먼저
  - PNG → JPEG로 줄여 `backend/static/story_images/`에 저장, URL은 `stories.scene_images.{n}` (scenes 배열과 따로라 다음 장면 저장과 안 겹침)
  - 실패하면 `scene_image_failed.{n}` → 그 장면은 그림 없이 진행, 같은 장면 동시 요청은 한 번만 그림
  - 화면: 그림 그리는 중 안내 → 장면 본문 위에 그림, 그림 없는 장면은 하나씩 차례로 요청
- [x] 팀원 기능 합침 (team/app-integration PR #10, 캐릭터·미디어)
  - 캐릭터 고르기 (`lib/widgets/character_strip.dart`, 16명) → `character_key` 저장, 이름을 Gemini 프롬프트에 주인공 이름으로
  - 캐릭터 장면 그림 `POST/GET /api/stories/{id}/scenes/{n}/image` (Cloudflare Workers AI → GridFS, `cloudflare_character.py`)
  - 장면 영상 `POST/GET .../scenes/{n}/video` (Hugging Face Space, `hf_space_video.py`), 완성 영상 `POST/GET .../journey-video`
  - 결말 화면: 🔊 동화 듣기 + 목소리 고르기 → 🎬 동화 영상 만들기 → 🌐 커뮤니티 공유
  - [ ] `.env`에 `CLOUDFLARE_CHARACTER_ENABLED`/`CLOUDFLARE_*`, `HF_VIDEO_SPACE_ENABLED`/`HF_*`가 없어서 지금은 503 안내만 (실제 그림·영상은 키 받은 뒤 확인)
  - [x] `GET /api/media/status` → `{image, video}`: 키가 없으면 화면에서 "장면 이미지 만들기"·"장면 영상 만들기"·"동화 영상 만들기" 버튼을 숨김
    (부를 때마다 `.env`를 다시 읽어서, 키를 넣으면 서버 재시작 없이 다음 화면부터 보임)
- [x] 선택지 버튼·"이야기 마무리하기": 진한 그라데이션 대신 은은하게 (색 12% 배경 + 40% 얇은 테두리 + 흰 글자, 팀원 `team/main` 선택지 느낌)
- [x] 동화 본문 낱말: 마우스를 올리면 진한 밑줄 + 은은한 배경 + 손가락 커서 (`_StoryWord`, 모든 장면), 터치 화면은 연한 밑줄 그대로
  - 외부 호출 시간 제한: Cloudflare 연결 5초·요청 40초·전체 60초, HF Space 연결 15초·전체 200초
  - 백엔드 추가 패키지: `pip install -r backend/requirements-media.txt`

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
- [x] 엔진 구조: 팀원 Colab 서버(STORY_SERVER_URL의 `/story/psych`, 150초) → Gemini 순
- [x] "놀이 속 선택을 바탕으로 한 참고용 이야기예요" 안내 (응답 `notice`, 목록·상세 모두 표시)
- [x] 화면 (하단 탭 "심리"): 맨 위 평균 성향 레이더 차트 + 점수 칩, 최근 5편 성향 변화 꺾은선(범례 눌러 선 켜고 끄기, 눌러서 점수 보기), 동화별 카드(돋보인 성향 + 요약)
- [x] 상세: 요약, 성향 막대그래프(성향별 고정 색 + 아래 숫자), 선택별 해석(고른 것 + 다른 길), 보호자 대화 질문 2개
- [x] 완료한 동화가 없으면 "동화를 끝까지 만들면 분석해 줄게요!" + "동화 만들러 가기"
- [x] 팀원 Colab 심리분석 서버 연결 (`RemotePsychEngine`): `choices_made` + `choice_emotions`(장면 만들 때 저장한 KOTE 감정) 전송
  - Colab 성향(모험적·친절함·용감함·창의적·협동심) → 우리 성향으로 변환 (용감함→용기, 친절함·협동심 평균→배려, 모험적→호기심, 창의적→창의성)
  - Colab에 없는 "신중함"은 비워 둠 (지어낸 점수 없음, 평균은 점수가 있는 동화끼리만, 상세 막대에는 "-")
  - Colab 원래 결과(유형·설명·주요 감정)는 `psych_analysis.colab`에 저장 → 상세 화면 "🤖 우리 팀 AI가 본 이야기 속 모습" 카드
  - 분석이 1~2분 걸려서 `GET /api/psych/me`는 백그라운드로 분석하고 20초만 기다림 (덜 끝나면 "살펴보는 중" → 다시 열면 결과)
  - [ ] 지금 Colab `/story/psych`가 3번 모두 "모델의 감정 분석 JSON을 읽지 못했습니다"(500)로 실패 → 팀원 쪽 확인 필요 (그동안은 Gemini로 넘어감)

## 우리 가족 목소리 / 동화 듣기 — `backend/voices.py`, `lib/pages/family_voice_page.dart`, `lib/pages/story_page.dart`
- [x] 마이페이지 "우리 가족 목소리": 이름(엄마·아빠·나…)을 붙여 최대 3개 등록·삭제 `GET/POST /api/voices`, `DELETE /api/voices/{id}`
  - 등록: 앱에서 바로 녹음(`record` 패키지, 웹·안드로이드, 따라 읽을 예시 문장 + 5~10초 안내) 또는 음성 파일 올리기(`file_picker`)
  - 서버가 형식과 상관없이 ffmpeg(PATH에 없으면 `imageio-ffmpeg`)로 WAV(PCM 16bit, 모노, 22.05kHz)로 변환, 앞뒤 무음 빼고 3초 미만이면 다시 녹음 안내, 20초까지만
  - 사용자별 폴더 `backend/voice_data/`에 저장 (static 밖이라 주소로 열 수 없음, git 제외), 메타는 `family_voices` 컬렉션
  - "녹음한 목소리는 동화 읽어주기에만 쓰이고, 언제든 지울 수 있어요" 안내, 지우면 그 목소리로 만든 오디오도 같이 삭제
- [x] 동화 듣기 `POST /api/tts {story_id, scene_number, voice_id}` (본문은 서버에 저장된 장면에서 읽음)
  - 목소리 목록 맨 앞은 항상 "기본 목소리(기계음)" = gTTS (예전 화면은 서버에 없는 `GET /api/tts`를 불렀음)
  - 가족 목소리 = Colab `POST /api/tts` (text + speaker_wav) → XTTS, Colab이 꺼져 있거나 실패하면 기본 목소리 + 안내
  - 만든 오디오는 `backend/static/tts/{목소리}/{해시}`에 저장 → 다시 들을 때 Colab·gTTS를 안 부름
  - 화면: "동화 듣기" 옆 목소리 고르기, 장면별로 차례로 읽기(다음 장면 미리 준비), 장면 카드마다 🔊 이 장면만 듣기
  - 가족 목소리가 없으면 "가족 목소리를 등록하면 그 목소리로 들을 수 있어요" + 등록 화면으로 가기

## Gemini 공통
- [x] 한도 초과(429) 시 대체 모델로 자동 재시도 (`backend/gemini_client.py`)
  - `.env`: `GEMINI_FALLBACK_MODELS=모델1,모델2` (쉼표로 구분), 429 난 모델은 10분 동안 건너뜀
  - 없어진 모델(404, 예: gemini-2.5-flash)도 건너뛰고 다음 모델로
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

## 단어 뜻풀이 Gemini 호출 줄이기
- [x] 국립국어원 사전이 우선인 구조 그대로, Gemini 없이 정할 수 있으면 바로 사전 뜻 (`word_meaning.decide_without_gemini`)
  - 사전 뜻 후보가 1개 → 그 뜻 (`[뜻풀이] 사전 1개`)
  - 클릭한 말의 형태로 품사 거르기: 조사가 붙은 말(무지개를) → 명사 뜻만, 관형형·활용형(귀여운, 노란) → 동사·형용사 뜻만. 1개 남으면 그 뜻 (`[뜻풀이] 품사로 결정`)
  - 조사/어미 둘 다 될 수 있는 말(토끼는 = 토끼+는 / 토끼다)은 둘 다 남겨서 Gemini가 문맥으로
  - 여러 개 남을 때만 Gemini가 문맥에 맞는 뜻을 고르고 다듬기 (`[뜻풀이] Gemini 선택`)
- [x] Gemini 없이 정한 결과는 문장이 달라도 같은 단어면 캐시 재사용 (`word_meaning_cache`의 sentence="")
- [x] 추천 단어도 사전 뜻이 1개인 단어는 Gemini에 넘기지 않음
