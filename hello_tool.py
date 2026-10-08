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
PHONE_URL = "https://www.fhehs.tp.edu.tw/about/%E9%9B%BB%E8%A9%B1%E5%88%86%E6%A9%9F/"
GENERAL_PHONE = "02-2732-1961"

# 芳和實中官方「電話分機」頁（2026-09-26 核對）
PHONE_DIRECTORY = {
    "校長室": "101", "家長會": "105", "人事室": "106", "會計室": "107",
    "課發中心主任": "201", "教學課務組": "202", "學習評量組": "206",
    "學資中心主任": "211", "圖書設備組": "212", "圖書室": "214", "系統管理組": "215",
    "學務中心主任": "301", "環保衛教組": "302", "生活教育組": "303",
    "運動推廣組": "304", "健康中心": "305", "外展探索中心": "321",
    "行政中心主任": "501", "文書組長": "502", "出納組長": "503", "警衛室": "505", "事務組長": "506",
    "輔導中心主任": "601", "輔導諮商組": "602", "生涯發展組": "602", "特殊教育組": "605",
    "七年級導師室": "325、326", "八年級導師室": "323、324",
    "九年級導師室": "323、324", "高中導師室": "331、332",
    "東區特教資源中心": "701~706、710、712", "教師會": "103", "會議室": "104",
}

PHONE_ALIASES = [
    (("生活教育組","生活輔導組","生輔組","生教組"), "生活教育組"),
    (("教學課務組","教務組","教學組"), "教學課務組"),
    (("課程發展中心","課發中心","教務處","教務中心"), "課發中心主任"),
    (("學生事務中心","學務處","學務中心"), "學務中心主任"),
    (("學生輔導中心","輔導室","輔導中心"), "輔導中心主任"),
    (("輔導諮商組","輔導組"), "輔導諮商組"),
    (("生涯發展組","生涯組"), "生涯發展組"),
    (("特殊教育組","特教組"), "特殊教育組"),
    (("環保衛教組","衛生組"), "環保衛教組"),
    (("運動推廣組","體育組"), "運動推廣組"),
    (("圖書設備組","設備組"), "圖書設備組"),
    (("系統管理組","資訊組"), "系統管理組"),
    (("圖書室","圖書館"), "圖書室"),
    (("人事室",), "人事室"), (("會計室",), "會計室"),
    (("校長室",), "校長室"), (("健康中心",), "健康中心"),
    (("警衛室",), "警衛室"), (("事務組",), "事務組長"),
    (("文書組",), "文書組長"), (("出納組",), "出納組長"),
    (("七年級導師室",), "七年級導師室"), (("八年級導師室",), "八年級導師室"),
    (("九年級導師室",), "九年級導師室"), (("高中導師室",), "高中導師室"),
]

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
    """分機採官方電話分機表精確對照；口語別名只用來導向芳和正式單位名稱。"""
    q = compact(query)

    if "總機" in q or q in ("芳和實中分機", "芳和分機", "學校電話", "芳和實中電話"):
        item = {
            "標題": "芳和實中｜總機",
            "原文摘錄": f"總機：{GENERAL_PHONE}",
            "官方來源": PHONE_URL,
            "來源類型": "official_phone_directory"
        }
        return [item]

    official = None
    for aliases, target in PHONE_ALIASES:
        if any(compact(a) in q for a in aliases):
            official = target
            break

    # 也允許直接輸入官方單位全名
    if official is None:
        for target in PHONE_DIRECTORY:
            if compact(target) in q:
                official = target
                break

    if official and official in PHONE_DIRECTORY:
        ext = PHONE_DIRECTORY[official]
        # 對主任/組長欄位，回答時使用較自然的芳和正式名稱
        display = {
            "課發中心主任": "課程發展中心主任",
            "學資中心主任": "學習資源中心主任",
            "學務中心主任": "學生事務中心主任",
            "行政中心主任": "行政管理中心主任",
            "輔導中心主任": "學生輔導中心主任",
            "事務組長": "事務組",
            "文書組長": "文書組",
            "出納組長": "出納組",
        }.get(official, official)
        item = {
            "標題": f"電話分機｜{display}",
            "原文摘錄": f"{display}：分機 {ext}；總機：{GENERAL_PHONE}",
            "官方來源": PHONE_URL,
            "來源類型": "official_phone_directory"
        }
        return [item]

    # 使用者只說「分機」但沒說單位時，回傳常用單位，避免丟出網站導覽。
    if "分機" in q or "電話" in q:
        common = ["生活教育組","教學課務組","學生事務中心主任","學生輔導中心主任"]
        # 上面兩個主任 display 需要從實際 key 取值
        rows = [
            f"生活教育組：303",
            f"教學課務組：202",
            f"學生事務中心主任：301",
            f"學生輔導中心主任：601",
        ]
        return [{
            "標題": "芳和實中｜常用電話分機",
            "原文摘錄": "；".join(rows) + f"；總機：{GENERAL_PHONE}",
            "官方來源": PHONE_URL,
            "來源類型": "official_phone_directory"
        }]

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
