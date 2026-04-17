"""Google API OAuth 인증 및 서비스 클라이언트 생성"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_DATA_DIR = os.getenv("DATA_DIR", ".")
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", os.path.join(_DATA_DIR, "credentials.json"))
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "/tmp/token.json")

# Secret Manager에서 주입된 token.json 내용을 파일로 기록
_token_json = os.getenv("GOOGLE_TOKEN_JSON")
if _token_json and not os.path.exists(TOKEN_PATH):
    with open(TOKEN_PATH, "w") as f:
        f.write(_token_json)


def get_calendar_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError("Google Calendar 인증 필요. /auth/start 엔드포인트로 재인증하세요.")

    return build("calendar", "v3", credentials=creds)
