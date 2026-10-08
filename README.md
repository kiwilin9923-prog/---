# Mini AI Assistant — MCP 教學範例

一個約 **300 行、一堂課讀得完** 的最小 AI 助理，讓你看懂三件事怎麼串起來：**LLM + MCP 工具呼叫 + Web 介面**。

工作坊 Segment 4 你會親手把它改成自己領域的助理（換資料、加工具）。

> 這是從中興大學「AI 學伴」（正式版 ~239 個工具）抽出來的最小骨架，只留核心、方便理解。

## ☁️ 最簡單：用 Colab 跑（零安裝，課堂推薦）

不想在自己電腦裝 Node / uv？點下面用 Google Colab，瀏覽器裡一步步按 ▶ 就能跑起完整的 web 助理並完成 L1：

**[▶ Open in Colab](https://colab.research.google.com/github/UDICatNCHU/nchu-mcp-workshop-2026/blob/main/mini-project/colab/workshop.ipynb)**

> 全部跑在雲端 Linux，Mac / Windows / 平板體驗一致，不會有「在我電腦上不能跑」的問題。需要一把講師發的 Claude API key。

想在自己電腦裝完整版的，往下看 ↓

## 架構

```
┌────────────┐   POST /chat    ┌──────────────┐   Claude API   ┌──────────────┐
│  瀏覽器    │ ──────────────> │  Express     │ ─────────────> │  Claude      │
│  (web/)    │ <────────────── │  (backend-   │ <───────────── │  (Anthropic) │
└────────────┘   {reply, ...}  │   node/)     │   tool_use?    └──────────────┘
                                │              │
                                │  MCPClient   │   stdio JSON-RPC
                                │              │ ──────────────────┐
                                └──────────────┘                   │
                                                                   ▼
                                                         ┌──────────────────┐
                                                         │  FastMCP server  │
                                                         │  (mcp-server-py/)│
                                                         │  讀 JSON 回傳    │
                                                         └──────────────────┘
```

三個模組，各自獨立可換：
| 模組 | 語言 | 檔案 | 職責 |
|------|------|------|------|
| MCP 工具伺服器 | Python | `mcp-server-py/*.py` | 定義工具、回傳資料 |
| Web 後端 | Node.js | `backend-node/*.js` | 轉接 LLM、管理 MCP client |
| 前端 | HTML + vanilla JS | `web/index.html` | 收發對話 |

**內建工具**（`config.json` 已註冊前 4 支）：
| 工具 | 檔案 | 說明 |
|------|------|------|
| `hello_tool` | `hello_tool.py` | 英文中心資訊（讀本機 JSON）— **L1 改造主例** |
| `teachers_tool` | `teachers_tool.py` | 教師查詢（mock 資料） |
| `weather_tool` | `weather_tool.py` | 天氣查詢 |
| `library_tool` | `library_tool.py` | 圖書館館藏即時查詢（Ex Libris Primo，**免 API key**）— **L3 外部 API 範例** |
| `course_tool` | `course_tool.py` | 中興 114-2 學期 **3018 門課**關鍵字搜尋 — **L4 大資料集範例** |
| `arxiv_tool` | `arxiv_tool.py` | arXiv 論文搜尋 — **L3 練習 stub**，故意未註冊，學員依手冊自己加 |

## 快速啟動（4 步）

> 先確認有安裝 [uv](https://docs.astral.sh/uv/) 和 Node.js 18+。

```bash
# 1. 安裝 Python 端（會自動建立 .venv）
cd mcp-server-py && uv sync && cd ..

# 2. 安裝 Node 端
cd backend-node && npm install && cd ..

# 3. 設定 API Key
cp .env.example .env
# 編輯 .env，填入從 https://console.anthropic.com/ 取得的 key

# 4. 啟動（會同時啟動 Python MCP server 做為子程序）
cd backend-node && npm start
```

瀏覽器打開 `http://localhost:3000`，試問：
- `英文中心幾點開門？`（→ 觸發 `hello_tool`，讀本機 JSON）
- `圖書館有沒有原子習慣這本書？`（→ 觸發 `library_tool`，即時打外部圖書館 API）

### Windows 學員看這邊

**最簡單路徑：裝 Git for Windows**（[git-scm.com/download/win](https://git-scm.com/download/win)），完成後用桌面的 **Git Bash** 跑上面 4 步，**體驗 100% 跟 Mac/Linux 一樣**（包括 `./setup.sh`）。

**純 PowerShell 路徑**（不裝 Git Bash 的話）：

```powershell
# 0. 先放行 PowerShell 跑 .ps1（一次性）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 1. 環境預檢（對等 ./setup.sh）
.\setup.ps1

# 2. 啟動
cd backend-node; npm start
```

Windows 常見指令對照：

| 做的事 | Mac / Linux / Git Bash | PowerShell |
|-------|----------------------|------------|
| 安裝 uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `irm https://astral.sh/uv/install.ps1 \| iex` |
| 編輯 .env | `nano .env` | `notepad .env` |
| 複製檔案 | `cp .env.example .env` | `Copy-Item .env.example .env` |
| 環境預檢 | `./setup.sh` | `.\setup.ps1` |
| 查 port | `lsof -i :3000` | `netstat -ano \| findstr :3000` |
| 殺進程 | `kill -9 <PID>` | `taskkill /F /PID <PID>` |

## 核心程式路徑

使用者送訊息後，資料流如下：

1. `web/index.html` 的 `send()` → `fetch('/chat', {messages})`
2. `backend-node/server.js` 的 `POST /chat` → `llm.chat(messages)`
3. `backend-node/llm-client.js` 的 `chat()`：呼叫 Claude API
4. Claude 回覆 `stop_reason === 'tool_use'` → 從 `mcp-client.js` 呼叫工具
5. `backend-node/mcp-client.js` 的 `callTool()` → 透過 stdio JSON-RPC 呼叫 Python
6. `mcp-server-py/hello_tool.py` 的 `get_english_center_info()` 回傳 JSON 字串
7. 結果塞回 `messages` 陣列，再呼叫一次 Claude API 請它總結
8. Claude 回覆 `stop_reason === 'end_turn'` → 取出 text，回傳給前端

**最重要的 20 行**：`llm-client.js:17-54` 的 tool-calling 迴圈。這是整個系統的靈魂。

## 如何做出你自己的 AI 助理

5 步驟：

### 1. 複製一支工具
```bash
cp mcp-server-py/hello_tool.py mcp-server-py/my_tool.py
```

### 2. 改工具
編輯 `my_tool.py`：
- 改 `FastMCP("hello_tool")` → `FastMCP("my_tool")`
- 改 `@mcp.tool()` 下的函式名稱與 docstring
- 改 `INFO = _load_data()` 與相關 JSON 檔，或直接把 JSON 換成你自己的邏輯（呼叫 API、查資料庫等）

**docstring 會變成 LLM 看到的工具說明**，寫清楚呼叫情境很重要。

### 3. 加進 config.json
```json
{
  "mcpServers": {
    "hello_tool": { ... },
    "my_tool": {
      "command": "uv",
      "args": ["--directory", "mcp-server-py", "run", "python", "my_tool.py"]
    }
  }
}
```

### 4. 重啟
```bash
# Ctrl-C 停掉 node，再 npm start
```
啟動 log 會印出 `✓ my_tool → ...`，代表工具已被 Claude 看見。

### 5. 測試
在網頁問相關問題 → Claude 會自己決定是否呼叫你的新工具。

---

## 這是教學最小版

為了「一堂課讀得完」，本範例只保留 MCP 串接的**核心**。真實上線的系統還會再加上對話持久化、多模型備援、速率限制與身份驗證、快取與部署等 —— 但這些都**不影響你理解 MCP 怎麼運作**。

想看一個真的上線、串了 ~239 個工具的完整版 → [中興 AI 學伴（線上版）](https://eduxplore.nlpnchu.org)。
