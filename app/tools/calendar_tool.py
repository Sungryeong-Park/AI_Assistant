"""Google Calendar에서 오늘 일정을 텍스트로 가져오는 툴"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict
from utils.auth import get_calendar_service


JST = timezone(timedelta(hours=9))


def get_today_events() -> List[Dict[str, str]]:
    """오늘 하루 일정을 [{time, title}] 형태로 반환합니다."""
    service = get_calendar_service()

    now = datetime.now(JST)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    result = []

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date", ""))
        title = event.get("summary", "(제목 없음)")

        # dateTime 형식인 경우 HH:MM만 추출
        if "T" in start:
            dt = datetime.fromisoformat(start)
            time_str = dt.strftime("%H:%M")
        else:
            time_str = "종일"

        result.append({"time": time_str, "title": title})

    return result
