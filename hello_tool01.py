#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fanghe_school")
BASE = Path(__file__).resolve().parent
INDEX = BASE / "data" / "fanghe_official_index.json"

def compact(s):
    return re.sub(r"\s+", "", str(s or "")).lower()

def bigrams(s):
    q = compact(s)
    runs = re.findall(r"[\u4e00-\u9fff]+", q)
    return {r[i:i+2] for r in runs for i in range(max(0, len(r)-1))}

def load():
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"records":[]}

INTENTS = [
    ("分機", ("分機","電話","總機","生輔","生活輔導","教務","學務","輔導","人事","會計","圖書館")),
    ("學生手冊", ("學生手冊","手冊")),
    ("請假", ("請假","假單","公假","病假","事假")),
    ("行動載具", ("行動載具","手機","載具")),
    ("獎懲", ("獎懲","嘉獎","小功","大功","警告","小過","大過")),
    ("行事曆", ("行事曆","行事历","行程","校務行事")),
]

TITLE_PREF = {
    "分機": ("分機","電話"),
    "學生手冊": ("學生手冊",),
    "請假": ("請假","學生手冊"),
    "行動載具": ("行動載具","手機","學生手冊"),
    "獎懲": ("獎懲","學生手冊"),
    "行事曆": ("行事曆","行事"),
}

def detect_intent(query):
    q = compact(query)
    for intent, words in INTENTS:
        if any(compact(w) in q for w in words):
            return intent
    return None

def excerpt_near(text, terms, width=850):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    positions = [text.find(t) for t in terms if t and text.find(t) >= 0]
    pos = min(positions) if positions else 0
    start = max(0, pos - 180)
    return text[start:start+width]

@mcp.tool()
def search_school_info(query: str) -> str:
    """查詢臺北市芳和實驗中學官方網站資料。只回傳官方索引可支持的內容。"""
    data = load()
    records = data.get("records", [])
    q = compact(query)
    qt = bigrams(query)
    intent = detect_intent(query)
    preferred = TITLE_PREF.get(intent, ())
    scored = []

    for r in records:
        raw_title = str(r.get("title",""))
        raw_text = str(r.get("text",""))
        title = compact(raw_title)
        hay = compact(raw_title + " " + raw_text)

        score = 0
        # 標題命中權重最高，避免大型首頁全文把真正文件擠掉
        for p in preferred:
            cp = compact(p)
            if cp and cp in title:
                score += 120
            elif cp and cp in hay:
                score += 18

        if title and (title in q or q in title):
            score += 45
        score += 3 * len(qt & bigrams(hay))

        # 查詢字詞直接命中
        for term in re.findall(r"[\u4e00-\u9fff]{2,}", query):
            ct = compact(term)
            if ct in title: score += 35
            elif ct in hay: score += 8

        # intent 必須至少有相關詞；泛首頁/分類頁降權
        if intent:
            intent_terms = TITLE_PREF[intent]
            if not any(compact(t) in hay for t in intent_terms):
                continue
        if r.get("url","").rstrip("/") == "https://www.fhehs.tp.edu.tw":
            score -= 35
        if "/category/" in str(r.get("url","")):
            score -= 12

        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    seen_urls = set()
    for score, r in scored:
        url = str(r.get("url",""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        terms = list(preferred) + re.findall(r"[\u4e00-\u9fff]{2,}", query)
        excerpt = excerpt_near(r.get("text",""), terms)
        out.append({
            "標題": r.get("title",""),
            "原文摘錄": excerpt,
            "官方來源": url,
            "來源類型": r.get("type","web"),
            "相關性": score
        })
        if len(out) >= 4:
            break

    result = {
        "查詢": query,
        "學校": "臺北市芳和實驗中學",
        "查詢類型": intent or "一般校務",
        "結果": out,
        "官方首頁": "https://www.fhehs.tp.edu.tw/"
    }
    if not out:
        result["錯誤"] = "目前芳和實中官方索引未找到足以支持此問題的資料；系統不自行補寫校規、電話或分機。"
    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()
