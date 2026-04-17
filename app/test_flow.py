"""전체 흐름 테스트

외부 API(Google Calendar, LINE)는 가짜 데이터로 대체.
Gemini(LLM + 검색)는 실제 호출 → GEMINI_API_KEY 필요.

실행 방법:
    .venv/bin/python test_flow.py
"""

import asyncio
import os
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# 모킹 데이터
# ---------------------------------------------------------------------------

MOCK_EVENTS = [
    {"time": "10:00", "title": "팀 미팅"},
    {"time": "14:00", "title": "외부 업체 미팅 (시부야)"},
]

MOCK_SEARCH = "東京目黒の今日の天気は曇り、午後から雨の予報です。降水確率60%。JR横浜線・東急目黒線は現在平常通り運転しています。"

INITIAL_PURCHASE_LIST = {
    "items": [
        {"name": "시금치", "quantity": "1단"},
        {"name": "보조배터리", "quantity": "1개"},
        {"name": "우유", "quantity": "2팩"}
    ]
}

sent_messages = []
current_input = ""


def reset_purchase_list():
    import json
    path = os.path.join(os.path.dirname(__file__), "data", "purchase_list.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(INITIAL_PURCHASE_LIST, f, ensure_ascii=False, indent=2)


def mock_send_line(text: str):
    sent_messages.append(text)
    label = current_input if current_input else "(스케줄러 자동 실행)"
    print(f"\n  입력: {label}")
    print(f"  응답:\n{text}")


# ---------------------------------------------------------------------------
# 테스트 1: 아침 브리핑
# ---------------------------------------------------------------------------

def test_morning_briefing():
    global current_input
    print("\n===== 테스트 1: 아침 브리핑 =====")
    sent_messages.clear()
    current_input = ""

    with patch("tools.calendar_tool.get_today_events", return_value=MOCK_EVENTS), \
         patch("tools.search_tool.search_weather_and_traffic", return_value=MOCK_SEARCH), \
         patch("tools.line_tool.send_line_message", side_effect=mock_send_line):

        from assistant_graph import run_morning_briefing
        run_morning_briefing()

    assert len(sent_messages) == 1, f"메시지 1개 기대, {len(sent_messages)}개 전송됨"
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 2: 구매 목록 추가
# ---------------------------------------------------------------------------

async def test_add_items():
    global current_input
    print("\n===== 테스트 2: 구매 목록 추가 =====")
    sent_messages.clear()
    current_input = "사과 2개랑 당근 추가해줘"

    with patch("tools.line_tool.send_line_message", side_effect=mock_send_line):
        from main import handle_text_message
        await handle_text_message(current_input)

    assert len(sent_messages) == 1
    assert "추가 완료" in sent_messages[0]
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 3: 구매 목록 삭제
# ---------------------------------------------------------------------------

async def test_remove_items():
    global current_input
    print("\n===== 테스트 3: 구매 목록 삭제 =====")
    sent_messages.clear()
    current_input = "우유 샀어"

    with patch("tools.line_tool.send_line_message", side_effect=mock_send_line):
        from main import handle_text_message
        await handle_text_message(current_input)

    assert len(sent_messages) == 1
    assert "삭제 완료" in sent_messages[0]
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 4: 품목 불명확 (되묻기)
# ---------------------------------------------------------------------------

async def test_add_unknown_item():
    global current_input
    print("\n===== 테스트 4: 품목 불명확 시 되묻기 =====")
    sent_messages.clear()
    current_input = "추가해줘"

    with patch("tools.line_tool.send_line_message", side_effect=mock_send_line):
        from main import handle_text_message
        await handle_text_message(current_input)

    assert len(sent_messages) == 1
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 5: 저녁 리마인더
# ---------------------------------------------------------------------------

def test_evening_reminder():
    global current_input
    print("\n===== 테스트 5: 저녁 리마인더 =====")
    sent_messages.clear()
    current_input = ""

    with patch("tools.line_tool.send_line_message", side_effect=mock_send_line):
        from main import run_evening_reminder
        run_evening_reminder()

    assert len(sent_messages) == 1
    assert "구매할 항목" in sent_messages[0]
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 6: 저녁 리마인더 - 목록 비어있을 때
# ---------------------------------------------------------------------------

def test_evening_reminder_empty():
    global current_input
    print("\n===== 테스트 6: 저녁 리마인더 - 목록 없을 때 =====")
    sent_messages.clear()

    with patch("main.load_purchase_list", return_value=[]), \
         patch("tools.line_tool.send_line_message", side_effect=mock_send_line):
        from main import run_evening_reminder
        run_evening_reminder()

    assert len(sent_messages) == 0, "목록 없으면 메시지 전송 안 해야 함"
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 7: userId 검증 - 타인 메시지 무시
# ---------------------------------------------------------------------------

async def test_user_id_filter():
    print("\n===== 테스트 7: 타인 userId 차단 =====")
    sent_messages.clear()

    with patch("tools.line_tool.send_line_message", side_effect=mock_send_line):
        from main import webhook
        from fastapi.testclient import TestClient
        from main import app
        import hmac, hashlib, base64, json

        body = json.dumps({
            "events": [{
                "type": "message",
                "source": {"userId": "U_STRANGER_ID"},
                "message": {"type": "text", "text": "우유 추가해줘"}
            }]
        }).encode()

        secret = os.getenv("LINE_CHANNEL_SECRET", "").encode()
        sig = base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode()

        client = TestClient(app)
        response = client.post("/webhook", content=body, headers={"X-Line-Signature": sig})

    assert response.status_code == 200
    assert len(sent_messages) == 0, "타인 메시지는 무시해야 함"
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 8: /run-now 토큰 검증
# ---------------------------------------------------------------------------

def test_run_now_auth():
    print("\n===== 테스트 8: /run-now 토큰 검증 =====")
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    res_no_token = client.post("/run-now")
    assert res_no_token.status_code == 403, "토큰 없으면 403이어야 함"

    res_wrong_token = client.post("/run-now", headers={"X-Admin-Token": "wrongtoken"})
    assert res_wrong_token.status_code == 403, "잘못된 토큰은 403이어야 함"

    print("PASS (실제 실행은 LINE 전송 포함이므로 토큰 검증만 확인)")


# ---------------------------------------------------------------------------
# 테스트 9: LINE 서명 없는 요청 → 400
# ---------------------------------------------------------------------------

def test_webhook_no_signature():
    print("\n===== 테스트 9: 서명 없는 webhook → 400 =====")
    import json
    from fastapi.testclient import TestClient
    from main import app

    body = json.dumps({"events": []}).encode()
    client = TestClient(app, raise_server_exceptions=False)

    res = client.post("/webhook", content=body)
    assert res.status_code == 400, f"서명 없으면 400이어야 함. 실제: {res.status_code}"
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 10: LINE 잘못된 서명 → 400
# ---------------------------------------------------------------------------

def test_webhook_wrong_signature():
    print("\n===== 테스트 10: 잘못된 서명 webhook → 400 =====")
    import json
    from fastapi.testclient import TestClient
    from main import app

    body = json.dumps({"events": []}).encode()
    client = TestClient(app, raise_server_exceptions=False)

    res = client.post("/webhook", content=body, headers={"X-Line-Signature": "invalidsignature"})
    assert res.status_code == 400, f"잘못된 서명은 400이어야 함. 실제: {res.status_code}"
    print("PASS")


# ---------------------------------------------------------------------------
# 테스트 11: /auth/start AUTH_SECRET 검증
# ---------------------------------------------------------------------------

def test_auth_start_protection():
    print("\n===== 테스트 11: /auth/start 보호 =====")
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, raise_server_exceptions=False)

    res_no_secret = client.get("/auth/start", follow_redirects=False)
    assert res_no_secret.status_code == 403, f"secret 없으면 403이어야 함. 실제: {res_no_secret.status_code}"

    res_wrong_secret = client.get("/auth/start?secret=wrongsecret", follow_redirects=False)
    assert res_wrong_secret.status_code == 403, f"잘못된 secret은 403이어야 함. 실제: {res_wrong_secret.status_code}"

    print("PASS")


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    reset_purchase_list()

    test_morning_briefing()
    asyncio.run(test_add_items())
    asyncio.run(test_remove_items())
    asyncio.run(test_add_unknown_item())
    test_evening_reminder()
    test_evening_reminder_empty()
    asyncio.run(test_user_id_filter())
    test_run_now_auth()
    test_webhook_no_signature()
    test_webhook_wrong_signature()
    test_auth_start_protection()

    print("\n===== 전체 테스트 완료 =====")
