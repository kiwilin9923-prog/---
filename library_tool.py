#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""圖書館館藏搜尋工具 — Lab 3 範例：呼叫真實外部 API（免 API key）。

示範重點：
  1. async def + httpx.AsyncClient — FastMCP 原生支援 async tools
  2. 呼叫真實 HTTP API（Ex Libris Primo 的公開 pnxs 端點，免 API key）
  3. JSON 解析 + 欄位清理（Primo 的 creator 欄帶 $$Q 標記要去掉）
  4. 三層錯誤處理：timeout / HTTP error / JSON parse
  5. 參數邊界檢查（limit 上下限）

機構設定用環境變數覆蓋，換學校只要改 4 個變數（預設中央大學）：
  PRIMO_HOST   例 ncu.primo.exlibrisgroup.com
  PRIMO_VID    例 886UST_NCU:886UST_NCU
  PRIMO_SCOPE  例 MyInstitution
  PRIMO_TAB    例 nculib

注意：你貼的「/discovery/search?...」是網頁介面(回 HTML),不是資料 API。
真正回 JSON 的是這支用的「/primaws/rest/pub/pnxs」公開端點。
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("library_tool")

# ── 機構設定（env var 可覆蓋,預設中央大學）─────────────
PRIMO_HOST = os.environ.get("PRIMO_HOST", "ncu.primo.exlibrisgroup.com")
PRIMO_VID = os.environ.get("PRIMO_VID", "886UST_NCU:886UST_NCU")
PRIMO_SCOPE = os.environ.get("PRIMO_SCOPE", "MyInstitution")
PRIMO_TAB = os.environ.get("PRIMO_TAB", "nculib")

TIMEOUT_SECONDS = 15.0
MAX_LIMIT = 20


def _clean(value: Any) -> str:
    """Primo 的 display 欄位多半是 list,且 creator 帶 '$$Q...' 標記。
    取第一個元素、砍掉 $$ 之後的內容、去頭尾空白與句點。"""
    if isinstance(value, list):
        value = value[0] if value else ""
    text = str(value).split("$$")[0].strip()
    return text.rstrip(" .")


def _extract_doc(doc: dict[str, Any]) -> dict[str, str]:
    """把一筆 Primo doc 轉成乾淨 dict（書名/作者/出版/年份/類型）。"""
    disp = doc.get("pnx", {}).get("display", {})
    return {
        "title": _clean(disp.get("title", "")),
        "creator": _clean(disp.get("creator", "")),
        "publisher": _clean(disp.get("publisher", "")),
        "year": _clean(disp.get("creationdate", "")),
        "type": _clean(disp.get("type", "")),
    }


@mcp.tool()
async def search_library(keyword: str, limit: int = 10) -> str:
    """搜尋大學圖書館館藏（書籍、期刊、論文等）。

    使用情境：使用者想知道圖書館有沒有某本書、某主題的館藏、
    或想找某作者的著作時呼叫。例如「圖書館有原子習慣這本書嗎？」、
    「館藏裡關於機器學習的書」、「有沒有村上春樹的小說」。

    Args:
        keyword: 搜尋關鍵字（書名、主題、作者皆可，中英文都支援）。
        limit: 最多回傳幾筆，預設 10，最大 20。

    回傳：館藏清單的 JSON，每筆含 title / creator / publisher / year / type，
    並附 total（總命中數）。無結果時 results 為空 list。
    """
    limit = max(1, min(limit, MAX_LIMIT))

    url = f"https://{PRIMO_HOST}/primaws/rest/pub/pnxs"
    params = {
        "q": f"any,contains,{keyword}",
        "vid": PRIMO_VID,
        "scope": PRIMO_SCOPE,
        "tab": PRIMO_TAB,
        "lang": "zh-tw",
        "offset": "0",
        "limit": str(limit),
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
    except httpx.TimeoutException:
        return json.dumps(
            {"error": f"圖書館 API 逾時（>{TIMEOUT_SECONDS}s），請稍後再試"},
            ensure_ascii=False,
        )
    except httpx.HTTPError as e:
        return json.dumps(
            {"error": f"圖書館 API 錯誤：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"回應格式錯誤：{e}"}, ensure_ascii=False)

    docs = data.get("docs", [])
    results = [_extract_doc(d) for d in docs]
    total = data.get("info", {}).get("total", len(results))

    return json.dumps(
        {"total": total, "showing": len(results), "results": results},
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
