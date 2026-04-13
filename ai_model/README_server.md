# 동화 AI 서버 실행 가이드

## 1. 패키지 설치

```bash
pip install fastapi uvicorn transformers peft torch accelerate bitsandbytes python-dotenv
```

## 2. 서버 실행

```bash
cd ai_model
python server.py
```

서버가 시작되면 모델 로딩에 1~3분 정도 소요됩니다.

## 3. 모드 선택

- **로컬 모델 (default)**: `final_model/` 폴더의 Qwen2.5-3B + LoRA 사용
- **Claude API**: `MODE=api ANTHROPIC_API_KEY=sk-... python server.py`

## 4. Flutter 앱 연결

`lib/services/api_service.dart` 에서 서버 주소 변경:
```dart
static const String baseUrl = 'http://내서버IP:8000';
```

## 5. Flutter 앱 실행

```bash
cd ..  # 프로젝트 루트
flutter pub get
flutter run
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET  | /health | 서버 상태 확인 |
| POST | /story/start | 새 동화 시작 |
| POST | /story/continue | 선택 후 이어쓰기 |
| POST | /story/choices | 선택지 생성 |
| POST | /story/vocab | 단어 추출 |
| POST | /story/psych | 심리 분석 |
