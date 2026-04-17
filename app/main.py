"""메구로 스마트 비서 - FastAPI 서버 (LINE Webhook + APScheduler)"""

import os
import json
import hmac
import hashlib
import base64
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from assistant_graph import run_morning_briefing
from tools.line_tool import send_line_message
from utils.file_manager import add_item, remove_item, load_purchase_list, format_purchase_list
from utils.auth import CREDENTIALS_PATH, TOKEN_PATH, SCOPES

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
APP_URL = os.getenv("APP_URL", "")

_oauth_states: dict[str, object] = {}

scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")


# ---------------------------------------------------------------------------
# 수명주기 관리
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 매일 아침 8시 브리핑 스케줄 등록
    scheduler.add_job(
        run_morning_briefing,
        CronTrigger(hour=8, minute=0, timezone="Asia/Tokyo"),
        id="morning_briefing",
        replace_existing=True,
    )
    scheduler.add_job(
        run_evening_reminder,
        CronTrigger(hour=20, minute=0, timezone="Asia/Tokyo"),
        id="evening_reminder",
        replace_existing=True,
    )
    scheduler.start()
    print("[스케줄러] 아침 8시 브리핑 / 저녁 8시 리마인더 등록 완료")
    yield
    scheduler.shutdown()


app = FastAPI(title="Meguro Smart Assistant", lifespan=lifespan)


# ---------------------------------------------------------------------------
# LINE Webhook 서명 검증
# ---------------------------------------------------------------------------

def verify_signature(body: bytes, signature: str) -> bool:
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# LINE Webhook 엔드포인트
# ---------------------------------------------------------------------------

def run_evening_reminder() -> None:
    items = load_purchase_list()
    if not items:
        return
    try:
        message = f"오늘 구매할 항목이 있습니다.\n\n{format_purchase_list(items)}"
        send_line_message(message)
    except Exception as e:
        print(f"[경고] 저녁 리마인더 전송 실패: {e}")


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)

    for event in payload.get("events", []):
        if event.get("type") != "message":
            continue
        if event["message"].get("type") != "text":
            continue

        if event.get("source", {}).get("userId") != os.getenv("ALLOWED_LINE_USER_ID"):
            continue

        text: str = event["message"]["text"].strip()
        asyncio.create_task(handle_text_message(text))

    return {"status": "ok"}


def _parse_intent(text: str, current_items: list) -> dict:
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=os.getenv("GEMINI_API_KEY"))

    current_list_text = "\n".join(f"- {i['name']}" for i in current_items) or "없음"

    prompt = f"""
사용자 메시지를 분석해서 아래 JSON 형식으로만 답해. 다른 텍스트 없이 JSON만 출력.

액션 종류:
- add: 구매 목록에 추가
- remove: 구매 목록에서 삭제 (구매완료 포함)
- list: 목록 조회
- unknown: 위에 해당 없음

규칙:
- 수량이 언급되지 않으면 "1개"로 설정.
- remove 액션일 때 품목명은 반드시 아래 현재 목록에 있는 이름 중 가장 유사한 것으로 매칭해서 사용.
- add 액션인데 품목을 특정할 수 없으면 items를 빈 배열로 반환.

현재 구매 목록:
{current_list_text}

출력 형식:
{{"action": "add", "items": [{{"name": "사과", "quantity": "2개"}}, {{"name": "당근", "quantity": "1개"}}]}}
{{"action": "remove", "items": [{{"name": "컵", "quantity": ""}}]}}
{{"action": "list", "items": []}}
{{"action": "unknown", "items": []}}

사용자 메시지: {text}
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"action": "unknown", "items": []}


async def handle_text_message(text: str) -> None:
    if not text.strip():
        return

    current_items = load_purchase_list()
    parsed = await asyncio.to_thread(_parse_intent, text, current_items)
    action = parsed.get("action")
    items = parsed.get("items", [])

    if action == "add":
        if not items:
            send_line_message("어떤 품목을 추가할까요?")
            return
        result_items = []
        for item in items:
            result_items = add_item(item["name"], item["quantity"])
        reply = f"추가 완료\n\n현재 목록:\n{format_purchase_list(result_items)}"

    elif action == "remove":
        result_items = current_items
        for item in items:
            result_items = remove_item(item["name"])
        reply = f"삭제 완료\n\n현재 목록:\n{format_purchase_list(result_items)}"

    elif action == "list":
        result_items = load_purchase_list()
        reply = f"현재 구매 목록:\n{format_purchase_list(result_items)}"

    else:
        reply = "어떤 품목을 추가 또는 삭제할까요?"

    send_line_message(reply)


# ---------------------------------------------------------------------------
# Google OAuth 인증 엔드포인트
# ---------------------------------------------------------------------------

def _get_flow(callback_url: str) -> Flow:
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        client_config = json.loads(base64.b64decode(credentials_json).decode())
        return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=callback_url)
    return Flow.from_client_secrets_file(CREDENTIALS_PATH, scopes=SCOPES, redirect_uri=callback_url)


@app.get("/auth/start")
def auth_start(secret: str = ""):
    if not AUTH_SECRET or secret != AUTH_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    callback_url = f"{APP_URL}/auth/callback"
    flow = _get_flow(callback_url)
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _oauth_states[state] = flow
    return RedirectResponse(auth_url)


@app.get("/auth/callback")
def auth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        raise HTTPException(status_code=400, detail=error)
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    flow = _oauth_states.pop(state)
    flow.fetch_token(code=code)
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(flow.credentials.to_json())
    return {"status": "인증 완료. token.json이 저장되었습니다."}


# ---------------------------------------------------------------------------
# 헬스체크 및 수동 실행
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run-now")
def run_now(request: Request):
    if request.headers.get("X-Admin-Token") != os.getenv("ADMIN_TOKEN"):
        raise HTTPException(status_code=403, detail="Forbidden")
    run_morning_briefing()
    return {"status": "briefing sent"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
