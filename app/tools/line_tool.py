"""LINE Messaging API로 메시지를 발송하는 툴"""

import os
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)


def send_line_message(text: str) -> bool:
    """지정된 사용자에게 텍스트 메시지를 전송합니다.

    Returns:
        성공 시 True, 실패 시 False
    """
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    if not token or not user_id:
        raise EnvironmentError("LINE_CHANNEL_ACCESS_TOKEN 또는 LINE_USER_ID 환경변수가 설정되지 않았습니다.")

    configuration = Configuration(access_token=token)

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(type="text", text=text)],
            )
        )

    return True
