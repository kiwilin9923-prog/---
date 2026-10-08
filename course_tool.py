#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""課程查詢工具 — L4 範例：在「大資料集」上做關鍵字搜尋。

示範重點（相較 L1 的單包 JSON、L2 的小清單）：
  1. 真實規模的資料 —— 中興大學 114-2 學期 3018 門課
  2. 多欄位關鍵字比對（科目名稱 / 教師 / 課程簡述）+ 系所篩選
  3. 為什麼要 limit:3000 筆全塞給 LLM 會爆 context,所以工具端先篩好再回
  4. docstring 寫清楚「使用情境」,讓 LLM 知道「找課」時要呼叫它

資料來源：中興大學課程查詢系統（公開），已抽出核心欄位 + 課程簡述。
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("course_tool")

_DATA_FILE = Path(__file__).parent / "data" / "courses_1142.json"
MAX_LIMIT = 30


def _load() -> list[dict]:
    if not _DATA_FILE.exists():
        return []
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


COURSES: list[dict] = _load()


@mcp.tool()
def search_courses(keyword: str, department: str = "", limit: int = 8) -> str:
    """搜尋中興大學 114-2 學期開課課程（共 3018 門）。

    使用情境：使用者想找某主題/某老師/某系的課，或問「有沒有教 X 的課」、
    「OO 老師開什麼課」、「資工系有哪些選修」時呼叫。

    Args:
        keyword: 關鍵字，會比對 科目名稱 / 上課教師 / 課程簡述（中文）。
        department: 選填，限定開課單位或系所（例如「資工」「文學院」「電機」）。
        limit: 最多回傳幾筆，預設 8，最大 30（資料量大，避免一次回太多）。

    回傳：符合的課程清單 JSON，每筆含 科目名稱 / 上課教師 / 學分數 /
    上課時間 / 上課教室 / 系所名稱 / 必選別 / 可加選餘額 / 課程簡述 /
    課程大綱URL。另附 total（總命中數）。無結果時 results 為空 list。
    """
    limit = max(1, min(limit, MAX_LIMIT))
    k = keyword.lower().strip()
    dept = department.strip()

    def hit(c: dict) -> bool:
        if dept and dept not in c.get("開課單位", "") and dept not in c.get("系所名稱", ""):
            return False
        blob = f"{c.get('科目名稱','')} {c.get('上課教師','')} {c.get('課程簡述','')}".lower()
        return k in blob

    matches = [c for c in COURSES if hit(c)] if k or dept else []
    return json.dumps(
        {"total": len(matches), "showing": min(len(matches), limit),
         "results": matches[:limit]},
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
