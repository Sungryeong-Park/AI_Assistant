"""Google Calendar 최초 인증 스크립트

Railway 배포 전 로컬에서 한 번 실행해서 token.json을 생성합니다.
생성된 token.json을 Railway Volume(/data)에 업로드하면
이후 서버에서 브라우저 없이 자동 갱신됩니다.

실행 방법:
    .venv/bin/python setup_auth.py
"""

from dotenv import load_dotenv
from utils.auth import get_calendar_service

load_dotenv()

if __name__ == "__main__":
    print("브라우저가 열리면 Google 계정으로 로그인 후 권한을 허용해주세요.")
    service = get_calendar_service()
    print("인증 완료. token.json이 생성되었습니다.")
    print("이 파일을 Railway Volume(/data)에 업로드하세요.")
