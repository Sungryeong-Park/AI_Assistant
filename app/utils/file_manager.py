"""구매 목록(purchase_list.json) 읽기/쓰기 유틸리티"""

import json
import os
from typing import List, Dict

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DATA_PATH = os.path.join(DATA_DIR, "purchase_list.json")


def load_purchase_list() -> List[Dict[str, str]]:
    if not os.path.exists(DATA_PATH):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        save_purchase_list([])
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", [])


def save_purchase_list(items: List[Dict[str, str]]) -> None:
    """구매 목록을 JSON 파일에 저장합니다."""
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, ensure_ascii=False, indent=2)


def add_item(name: str, quantity: str) -> List[Dict[str, str]]:
    """품목을 추가하고 갱신된 목록을 반환합니다."""
    items = load_purchase_list()
    # 이미 같은 이름이 있으면 수량 업데이트
    for item in items:
        if item["name"] == name:
            item["quantity"] = quantity
            save_purchase_list(items)
            return items
    items.append({"name": name, "quantity": quantity})
    save_purchase_list(items)
    return items


def remove_item(name: str) -> List[Dict[str, str]]:
    """품목명으로 항목을 삭제하고 갱신된 목록을 반환합니다."""
    items = load_purchase_list()
    items = [item for item in items if item["name"] != name]
    save_purchase_list(items)
    return items


def format_purchase_list(items: List[Dict[str, str]]) -> str:
    """구매 목록을 '품목: 수량' 형식의 문자열로 변환합니다."""
    if not items:
        return "구매할 항목이 없습니다."
    return "\n".join(f"* {item['name']}: {item['quantity']}" for item in items)
