import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage


def search_weather_and_traffic() -> str:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )
    llm_with_search = llm.bind(tools=[{"google_search": {}}])

    prompt = (
        "東京目黒の今日の天気予報（降水確率、気温）と、"
        "JR横浜線と東急目黒線の大規模な遅延・運休・障害情報を教えてください。"
        "日本語で簡潔に答えてください。"
    )

    response = llm_with_search.invoke([HumanMessage(content=prompt)])
    content = response.content
    if isinstance(content, list):
        content = "\n".join(str(c) for c in content if c)
    return content
