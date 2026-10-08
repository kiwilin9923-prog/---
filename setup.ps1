<#
.SYNOPSIS
  setup.ps1 — Windows PowerShell 版的工作坊環境預檢腳本(對應 setup.sh)
.DESCRIPTION
  用法:在 mini-project/ 根目錄 PowerShell 跑 `.\setup.ps1`

  跟 setup.sh 同樣 5 個 section:
    1. 基本工具:Node ≥18 / npm / uv / python 3.11+
    2. 專案檔案完整性
    3. .env 與 ANTHROPIC_API_KEY
    4. 依賴安裝(npm + uv sync)
    5. 啟動驗證(6 秒 boot test)

  全部 ✅ = 上課可直接 hands-on。有任何 ❌ = 先處理再重跑。

.NOTES
  作者: NCHU MCP Workshop
  Windows 用 Git Bash 也可以直接跑 setup.sh — 這支 .ps1 是給「不裝 Git Bash 純 PowerShell」的人用。
#>

$ErrorActionPreference = "Continue"
Set-Location -Path (Split-Path $MyInvocation.MyCommand.Path)

# ── 計數器 ──────────────────────────────
$script:Pass = 0
$script:Fail = 0
$script:Warn = 0

function Ok($msg)       { Write-Host "[OK] $msg" -ForegroundColor Green; $script:Pass++ }
function Bad($msg, $hint = "") {
    Write-Host "[!!] $msg" -ForegroundColor Red
    if ($hint) { Write-Host "     -> $hint" -ForegroundColor DarkGray }
    $script:Fail++
}
function Warn($msg, $hint = "") {
    Write-Host "[~~] $msg" -ForegroundColor Yellow
    if ($hint) { Write-Host "     -> $hint" -ForegroundColor DarkGray }
    $script:Warn++
}
function Section($name) { Write-Host ""; Write-Host "-- $name --" -ForegroundColor Cyan }

# ── 1. 基本工具 ────────────────────────
Section "1/5 基本工具"

# Node
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = (& node --version) -replace 'v',''
    $nodeMajor = [int]($nodeVer.Split('.')[0])
    if ($nodeMajor -ge 18) {
        Ok "Node v$nodeVer"
    } else {
        Bad "Node v$nodeVer (需 >=18)" "https://nodejs.org/ 下載 LTS 版"
    }
} else {
    Bad "node 未安裝" "https://nodejs.org/ 下載 LTS 安裝程式"
}

# npm
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Ok "npm $(npm --version)"
} else {
    Bad "npm 未安裝(通常會跟 Node 一起裝)"
}

# uv
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = (& uv --version) -split ' '
    Ok "uv $($uvVer[1])"
} else {
    Bad "uv 未安裝" "PowerShell 跑: irm https://astral.sh/uv/install.ps1 | iex"
}

# Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = (& python --version) -split ' '
    $pyMajor = [int]($pyVer[1].Split('.')[0])
    $pyMinor = [int]($pyVer[1].Split('.')[1])
    if ($pyMajor -ge 3 -and $pyMinor -ge 11) {
        Ok "Python $($pyVer[1])"
    } else {
        Warn "Python $($pyVer[1]) < 3.11" "uv sync 會嘗試自動安裝符合版本"
    }
} else {
    Warn "python 未直接安裝" "uv 會自動解決"
}

# ── 2. 專案檔案完整性 ──────────────────
Section "2/5 專案結構"

$coreFiles = @(
    "config.json",
    "backend-node\package.json",
    "backend-node\server.js",
    "backend-node\mcp-client.js",
    "backend-node\llm-client.js",
    "mcp-server-py\pyproject.toml",
    "mcp-server-py\hello_tool.py",
    "mcp-server-py\data\english_center.json",
    "web\index.html"
)

$missing = 0
foreach ($f in $coreFiles) {
    if (-not (Test-Path $f)) {
        Bad "$f 不存在"
        $missing++
    }
}
if ($missing -eq 0) { Ok "9 個核心檔案齊全" }

# ── 3. API Key 與 .env ────────────────
Section "3/5 API Key 與 .env"

if (Test-Path ".env") {
    Ok ".env 檔已建立"
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match '^\s*ANTHROPIC_API_KEY=sk-ant-[A-Za-z0-9_-]{20,}' -or
        $envContent -match 'ANTHROPIC_API_KEY=sk-ant-[A-Za-z0-9_-]{20,}') {
        Ok "ANTHROPIC_API_KEY 格式正確"
    } elseif ($envContent -match 'ANTHROPIC_API_KEY=sk-ant-\.\.\.') {
        Bad ".env 的 ANTHROPIC_API_KEY 還是範例 placeholder" "用 notepad 編輯 .env 填入真實 key"
    } elseif ($envContent -match 'ANTHROPIC_API_KEY=') {
        Warn ".env 的 ANTHROPIC_API_KEY 格式看起來異常" "key 應以 sk-ant- 開頭,不要加引號"
    } else {
        Bad ".env 沒有 ANTHROPIC_API_KEY 這行"
    }
} elseif ($env:ANTHROPIC_API_KEY) {
    Warn ".env 不存在(但環境變數已設)" "建議 Copy-Item .env.example .env"
} else {
    Bad ".env 不存在且 ANTHROPIC_API_KEY 環境變數未設" "Copy-Item .env.example .env 後編輯填 key"
}

# ── 4. 依賴安裝 ───────────────────────
Section "4/5 依賴安裝"

if (Test-Path "backend-node\node_modules") {
    Ok "Node 依賴已安裝"
} else {
    Write-Host "   首次執行,安裝 Node 依賴 (約 30 秒)..."
    Push-Location backend-node
    $npmLog = "$env:TEMP\mini-npm.log"
    npm install *> $npmLog
    if ($LASTEXITCODE -eq 0) {
        Ok "npm install 完成"
    } else {
        Bad "npm install 失敗" "看 $npmLog"
    }
    Pop-Location
}

if (Test-Path "mcp-server-py\.venv") {
    Ok "Python 依賴已安裝"
} else {
    Write-Host "   首次執行,安裝 Python 依賴 (約 30 秒)..."
    Push-Location mcp-server-py
    $uvLog = "$env:TEMP\mini-uv.log"
    uv sync *> $uvLog
    if ($LASTEXITCODE -eq 0) {
        Ok "uv sync 完成"
    } else {
        Bad "uv sync 失敗" "看 $uvLog"
    }
    Pop-Location
}

# ── 5. Boot 驗證 ──────────────────────
Section "5/5 啟動驗證 (6 秒)"

# 檢查 port 3000 是否被佔用
$portInUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($portInUse) {
    Bad "port 3000 已被其他程式佔用" "netstat -ano | findstr :3000 找出 PID -> taskkill /F /PID <PID>"
} elseif ($script:Fail -gt 0) {
    Warn "跳過啟動驗證" "前面有項目未通過,先修好再跑"
} else {
    Push-Location backend-node
    $bootLog = "$env:TEMP\mini-setup-boot.log"
    $bootProc = Start-Process -FilePath "node" -ArgumentList "server.js" `
                              -NoNewWindow -PassThru `
                              -RedirectStandardOutput $bootLog `
                              -RedirectStandardError "$bootLog.err"

    Start-Sleep -Seconds 6

    $logContent = ""
    if (Test-Path $bootLog) { $logContent = Get-Content $bootLog -Raw }

    if ($logContent -match "Mini AI Assistant:") {
        Ok "Express server 啟動"
        if ($logContent -match "✓ hello_tool") {
            Ok "MCP server 連線成功 (hello_tool 工具已載入)"
        } else {
            Bad "MCP server 連線失敗" "type $bootLog"
        }
    } else {
        Bad "server 無法啟動" "type $bootLog"
    }

    if ($bootProc -and -not $bootProc.HasExited) {
        Stop-Process -Id $bootProc.Id -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}

# ── 總結 ──────────────────────────────
Write-Host ""
Write-Host "----------------------------------------"
Write-Host "結果:" -NoNewline
Write-Host " $($script:Pass) [OK]" -ForegroundColor Green -NoNewline
Write-Host "   $($script:Warn) [~~]" -ForegroundColor Yellow -NoNewline
Write-Host "   $($script:Fail) [!!]" -ForegroundColor Red

if ($script:Fail -gt 0) {
    Write-Host "環境尚未就緒,請修正後重跑 .\setup.ps1" -ForegroundColor Red
    exit 1
} else {
    Write-Host "環境 OK!上課時直接 cd backend-node; npm start" -ForegroundColor Green
}
