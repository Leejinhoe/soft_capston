1. 실행전 구글 드라이브 데이터베이스 폴더에서 .env파일, database.py  다운로드 받기 
2. .env 파일은 pubspec.yaml과 같은위치, database.py는 DB연결 테스트 폴더로 옮기기
3. 데이터베이스 저장을 위해 터미널 하나는 main.py가 있는 DB연결 테스트로 이동해서 uvicorn main:app --reload으로 실행하기
4. 로그인 확인은 flutter pub get 이후 flutter run -d chrome --web-port 3000 으로 실행하기