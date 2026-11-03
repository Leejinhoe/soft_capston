1. 실행전 구글 드라이브 데이터베이스 폴더에서 .env파일, database.py  다운로드 받기
2. .env 파일은 pubspec.yaml과 같은 위치에 두고, database.py는 backend 폴더에 둡니다.
3. 데이터베이스 저장을 위해 터미널에서 backend 폴더로 이동한 후 uvicorn main:app --reload로 실행합니다.
4. 로그인 확인은 flutter pub get 이후 flutter run -d chrome --web-port 3000 으로 실행하기
