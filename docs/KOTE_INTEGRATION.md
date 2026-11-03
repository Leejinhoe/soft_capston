# KOTE 감정분석 연동

동화 생성은 기존 이야기 서버에서 계속 수행합니다. 생성 성공 후 Flutter의 ApiService가 DB_API_BASE_URL의 `/api/emotions/analyze`에 정리된 선택지와 본문을 보냅니다. 선택지는 단독 분석하고, 본문도 별도로 분석합니다. 선택한 이전 행동은 selected_choice_emotion으로 연결됩니다.

## 로컬 실행
- 기존 DB FastAPI 실행 방법은 동일합니다. 선택 의존성은 `backend/requirements-emotion.txt`에 분리했습니다. 학습이나 로컬 GPU는 사용하지 않습니다.
- 현재 컴퓨터는 `D:\New project 2\emotion_checkpoint`의 모델과 캐시된 토크나이저를 사용합니다. 다른 컴퓨터에서는 프로젝트 `models/emotion_checkpoint`에 모델을 두거나 서버 환경변수 `KOTE_MODEL_PATH`로 경로를 지정합니다. 모델 가중치는 Git에 올리지 않습니다.
- 토크나이저는 beomi/KcELECTRA-base-v2022를 로컬 캐시에서만 읽고 토큰 ID 지문을 검사합니다. 캐시가 없으면 분석을 비활성 상태로 응답합니다. 서버 실행 중 임의 다운로드하지 않습니다.
- `GET /api/emotions/health`에서 모델 로드 여부를 확인합니다. 첫 분석 요청에서 모델을 한 번 로드합니다.
- `POST /api/emotions/analyze` 예: `{"story_text":"기쁜 하루였다.","choices":["나는 정말 기쁘고 행복하다."],"selected_choice":"친구에게 고맙다고 말한다."}`

## 표시와 저장
없음/감정이 함께 기준을 넘거나 점수가 낮으면 확정 감정을 표시하지 않습니다. 모델 부재/입력 초과/연결 실패는 동화 생성을 실패시키지 않습니다. 불확실한 결과는 선택지 인덱스를 유지하며 null로 보냅니다. 본문/선택 감정은 기존 scenes 저장 경로로 전달됩니다. 실제 MongoDB 저장·재로그인 후 API 재조회 및 Flutter 복원 검사를 통과했습니다.

기존 LLM 감정점수를 무조건 켜는 변경이 아닙니다. 원래 서버의 점수는 계속 지우고, 이번 KOTE 경로에서 받은 결과만 허용합니다. 심리 진단용 LLM 요청의 emotion_scoring_enabled=false는 유지합니다.

## 검증 범위와 한계
실제 MongoDB와 safetensors로 테스트 계정 로그인→선택지 분석→두 장면 저장→읽기 상태 저장→재로그인→재조회 검사를 통과했습니다. 이 실제 응답을 Flutter StorySession으로 복원하는 검사도 통과했습니다. 서버8개, Flutter 연동/복원/기존 생성요청12개 검사가 통과했습니다. 준비한 본문을 사용한 API 검사이며 실제 LLM 생성·브라우저 버튼 클릭 검증은 아닙니다.

재현: 프로젝트에서 `python -B -X utf8 tools/run_kote_mongo_e2e.py --allow-test-writes`를 실행합니다. 테스트 계정1개와 동화1개를 실제 DB에 생성하므로 명시적 옵션 없이는 실행하지 않습니다. 결과는 Git에서 제외된 output/kote_mongo_e2e_실행ID.json에 저장합니다. 해당 파일을 `flutter test --no-pub --dart-define=KOTE_E2E_REPORT=결과파일경로 test/kote_mongo_restore_test.dart`로 넘기면 실제 응답의 Flutter 복원을 검증합니다. 생성한 테스트 문서는 자동 삭제하지 않습니다.

44라벨 순서는 기존 서버와 공유하는 KOTE 목록을 사용합니다. 현재 checkpoint config는 일반 LABEL_n이므로 학습 당시 라벨·토크나이저 출처에 대한 독립 검증의 한계는 남습니다. 이 모델의 점수는 보정된 정확도나 아이의 감정 확률이 아닙니다. 신규 학습·모델 정확도 향상을 주장하지 않습니다.
