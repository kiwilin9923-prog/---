#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fanghe_school")
BASE = Path(__file__).resolve().parent
INDEX = BASE / "data" / "fanghe_official_index.json"

OFFICIAL_HOME = "https://www.fhehs.tp.edu.tw/"
STUDENT_AFFAIRS_URL = "https://www.fhehs.tp.edu.tw/category/office/div_300/"
CALENDAR_URL = "https://www.fhehs.tp.edu.tw/calendar/"

def compact(s):
    return re.sub(r"\s+", "", str(s or "")).lower()

def normalize_text(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def load():
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"records":[]}

def detect_intent(query):
    q = compact(query)
    # 先判斷較具體意圖，避免「生活輔導組分機」只被泛化成一般查詢
    if any(x in q for x in ("分機","電話","總機","生輔","生活輔導","生活教育組","教務","學務","輔導室","人事","會計")):
        return "分機"
    if any(x in q for x in ("學生手冊","手冊")):
        return "學生手冊"
    if any(x in q for x in ("請假","假單","公假","病假","事假")):
        return "請假"
    if any(x in q for x in ("行動載具","手機規定","手機管理","載具")):
        return "行動載具"
    if any(x in q for x in ("獎懲","嘉獎","小功","大功","警告","小過","大過")):
        return "獎懲"
    if any(x in q for x in ("行事曆","行事历","校務行事","本週行事","本周行事")):
        return "行事曆"
    return "一般校務"

def find_record(records, *, url=None, title_contains=None):
    if url:
        target = url.rstrip("/")
        for r in records:
            if str(r.get("url","")).rstrip("/") == target:
                return r
    if title_contains:
        for r in records:
            title = str(r.get("title",""))
            if all(x in title for x in title_contains):
                return r
    return None

def window(text, anchors, before=80, after=300):
    text = normalize_text(text)
    if not text:
        return ""
    positions = []
    for a in anchors:
        if not a:
            continue
        p = text.find(a)
        if p >= 0:
            positions.append(p)
    if not positions:
        return ""
    p = min(positions)
    return text[max(0, p-before): min(len(text), p+after)].strip()

def section_window(text, start_anchor, end_anchors=(), max_chars=520):
    text = normalize_text(text)
    p = text.find(start_anchor)
    if p < 0:
        return ""
    end = min(len(text), p + max_chars)
    for a in end_anchors:
        ep = text.find(a, p + len(start_anchor))
        if ep >= 0:
            end = min(end, ep)
    return text[p:end].strip()

def make_item(record, excerpt, title=None):
    return {
        "標題": title or record.get("title",""),
        "原文摘錄": excerpt,
        "官方來源": record.get("url",""),
        "來源類型": record.get("type","web")
    }

def phone_result(query, records):
    q = compact(query)
    affairs = find_record(records, url=STUDENT_AFFAIRS_URL)
    if not affairs:
        return []

    text = normalize_text(affairs.get("text",""))

    # 使用者常口語說「生活輔導組」；官方頁面實際名稱為「生活教育組」，
    # 同頁另列「學生生活輔導及轉介」人員。保留兩者原文，避免自行等同。
    if any(x in q for x in ("生活輔導","生輔","生活教育")):
        excerpt = section_window(
            text, "生活教育組",
            end_anchors=("環保衛教組",),
            max_chars=620
        )
        return [make_item(
            affairs, excerpt,
            "學生事務中心｜生活教育組／學生生活輔導"
        )] if excerpt else []

    # 其他分機查詢：先在學生事務中心頁尋找使用者提到的單位
    aliases = [
        ("學生事務中心", "學生事務中心"),
        ("學務", "學生事務中心"),
        ("環保衛教", "環保衛教組"),
    ]
    for user_term, official_term in aliases:
        if compact(user_term) in q:
            excerpt = section_window(text, official_term, max_chars=430)
            if excerpt:
                return [make_item(affairs, excerpt, f"學生事務中心｜{official_term}")]

    # 若索引沒有該單位的精確分機頁，不拿網站導覽冒充答案
    return []

def manual_result(records):
    # 現有索引只證明官網有「115學年度學生手冊」入口，
    # 沒有同步到手冊正文，因此只回傳入口附近原文，不推測內容。
    home = find_record(records, url=OFFICIAL_HOME)
    if not home:
        return []
    excerpt = window(home.get("text",""), ["115學年度學生手冊"], before=110, after=180)
    return [make_item(home, excerpt, "115學年度學生手冊｜官網入口")] if excerpt else []

def leave_result(records):
    affairs = find_record(records, url=STUDENT_AFFAIRS_URL)
    if not affairs:
        return []
    text = normalize_text(affairs.get("text",""))
    excerpt = section_window(text, "生活教育組", end_anchors=("環保衛教組",), max_chars=620)
    if "請假" not in excerpt:
        excerpt = window(text, ["學生請假","請假"], before=120, after=300)
    return [make_item(affairs, excerpt, "學生事務中心｜請假相關業務")] if excerpt else []

def discipline_result(query, records):
    affairs = find_record(records, url=STUDENT_AFFAIRS_URL)
    if not affairs:
        return []
    text = normalize_text(affairs.get("text",""))
    q = compact(query)

    # 問到「小過/大過/警告」的具體條件時，現有索引沒有條文，不以一般獎懲職掌冒充規定。
    specific = [x for x in ("小過","大過","警告","小功","大功","嘉獎") if x in q]
    if specific and not any(x in text for x in specific):
        return []

    excerpt = section_window(text, "生活教育組", end_anchors=("環保衛教組",), max_chars=560)
    if "獎懲" not in excerpt:
        excerpt = window(text, ["獎懲"], before=140, after=260)
    return [make_item(affairs, excerpt, "學生事務中心｜學生品德考查獎懲業務")] if excerpt else []

def calendar_result(records):
    rec = find_record(records, url=CALENDAR_URL)
    if not rec:
        return []
    text = normalize_text(rec.get("text",""))
    excerpt = window(text, ["115行事曆總表","學校行事曆"], before=80, after=330)
    return [make_item(rec, excerpt, "115學年度學校行事曆")] if excerpt else []

def generic_result(query, records):
    # 一般查詢採保守模式：標題直接命中才回傳，避免大型導覽頁全文誤命中。
    q = compact(query)
    scored = []
    for r in records:
        title = compact(r.get("title",""))
        if not title:
            continue
        score = 0
        if q and q in title:
            score += 100
        for term in re.findall(r"[\u4e00-\u9fff]{2,}", query):
            if compact(term) in title:
                score += 25
        if "網站導覽" in str(r.get("title","")):
            score -= 200
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, r in scored[:2]:
        excerpt = window(r.get("text",""), re.findall(r"[\u4e00-\u9fff]{2,}", query), 70, 260)
        out.append(make_item(r, excerpt))
    return out

@mcp.tool()
def search_school_info(query: str) -> str:
    """查詢臺北市芳和實驗中學官方索引；資料不足時明確回報，不自行補寫。"""
    data = load()
    records = data.get("records", [])
    intent = detect_intent(query)

    if intent == "分機":
        out = phone_result(query, records)
    elif intent == "學生手冊":
        out = manual_result(records)
    elif intent == "請假":
        out = leave_result(records)
    elif intent == "行動載具":
        # 目前索引沒有行動載具/手機管理規定正文；網站導覽中的「手機」是無障礙說明，不可當校規。
        out = []
    elif intent == "獎懲":
        out = discipline_result(query, records)
    elif intent == "行事曆":
        out = calendar_result(records)
    else:
        out = generic_result(query, records)

    result = {
        "查詢": query,
        "學校": "臺北市芳和實驗中學",
        "查詢類型": intent,
        "結果": out,
        "官方首頁": OFFICIAL_HOME
    }
    if not out:
        result["錯誤"] = (
            "目前已同步的芳和實中官方索引沒有足以支持此問題的精確資料；"
            "系統不以網站導覽文字冒充答案，也不自行補寫校規、電話或分機。"
        )
    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()
