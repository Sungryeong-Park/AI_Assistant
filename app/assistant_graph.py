"""LangGraph 워크플로우: 상태 관리 및 노드 연결"""

import operator
import os
from typing import TypedDict, List, Dict, Annotated
from langgraph.graph import StateGraph, END, START
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from tools.calendar_tool import get_today_events
from tools.search_tool import search_weather_and_traffic
from tools.line_tool import send_line_message
from utils.file_manager import load_purchase_list, format_purchase_list


class AssistantState(TypedDict):
    events: List[Dict[str, str]]
    search_results: str
    purchase_items: List[Dict[str, str]]
    final_message: str
    errors: Annotated[List[str], operator.add]


def fetch_calendar(state: AssistantState) -> dict:
    try:
        return {"events": get_today_events()}
    except Exception as e:
        return {"events": [], "errors": [f"캘린더 오류: {e}"]}


def fetch_search(state: AssistantState) -> dict:
    try:
        return {"search_results": search_weather_and_traffic()}
    except Exception as e:
        return {"search_results": "", "errors": [f"검색 오류: {e}"]}


def fetch_purchase_list(state: AssistantState) -> dict:
    try:
        return {"purchase_items": load_purchase_list()}
    except Exception as e:
        return {"purchase_items": [], "errors": [f"구매 목록 오류: {e}"]}


def format_message(state: AssistantState) -> dict:
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3, google_api_key=os.getenv("GEMINI_API_KEY"))

        events_text = "\n".join(
            f"- {e['time']} {e['title']}" for e in state["events"]
        ) or "오늘 일정이 없습니다."

        purchase_text = format_purchase_list(state["purchase_items"])

        prompt = f"""
당신은 친절한 개인 비서입니다. 아래 정보를 바탕으로 아침 브리핑 메시지를 한국어로 작성해주세요.

[날씨 및 교통 정보]
{state["search_results"]}

[오늘 일정]
{events_text}

[구매 목록]
{purchase_text}

출력 형식 (이모지 포함, 텍스트만):
📢 좋은 아침입니다! (도쿄 메구로)

🌤️ 날씨 & 교통
* 날씨 요약 (한 줄)
* JR요코하마선: 상태 / 도큐메구로선: 상태

📅 오늘 일정
* HH:MM 일정명
...

🛒 구매 확인 항목
* 품목: 수량
...

※ 날씨/교통 상황을 고려한 한 줄 조언
"""

        response = llm.invoke([HumanMessage(content=prompt)])
        return {"final_message": response.content}
    except Exception as e:
        return {"errors": [f"메시지 생성 오류: {e}"]}


def send_message(state: AssistantState) -> dict:
    if not state.get("final_message"):
        return {"errors": ["전송 스킵: 메시지 없음"]}
    try:
        send_line_message(state["final_message"])
        return {}
    except Exception as e:
        return {"errors": [f"LINE 전송 오류: {e}"]}


def build_graph() -> StateGraph:
    graph = StateGraph(AssistantState)

    graph.add_node("fetch_calendar", fetch_calendar)
    graph.add_node("fetch_search", fetch_search)
    graph.add_node("fetch_purchase_list", fetch_purchase_list)
    graph.add_node("format_message", format_message)
    graph.add_node("send_message", send_message)

    # 3개 노드 병렬 실행
    graph.add_edge(START, "fetch_calendar")
    graph.add_edge(START, "fetch_search")
    graph.add_edge(START, "fetch_purchase_list")

    # 3개 완료 후 순차 실행
    graph.add_edge("fetch_calendar", "format_message")
    graph.add_edge("fetch_search", "format_message")
    graph.add_edge("fetch_purchase_list", "format_message")
    graph.add_edge("format_message", "send_message")
    graph.add_edge("send_message", END)

    return graph.compile()


assistant_graph = build_graph()


def run_morning_briefing() -> None:
    initial_state: AssistantState = {
        "events": [],
        "search_results": "",
        "purchase_items": [],
        "final_message": "",
        "errors": [],
    }
    result = assistant_graph.invoke(initial_state)
    for err in result.get("errors", []):
        print(f"[경고] {err}")
    print("[완료] 아침 브리핑 전송 완료")
