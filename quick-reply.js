// 免呼叫 Gemini 的輕量查詢：台灣日期/星期，以及既有天氣 MCP。
const TIME_ZONE = 'Asia/Taipei';

function isDateOrWeekdayQuestion(query) {
  return /星期幾|禮拜幾|週幾|今天幾號|今日幾號|今天日期|今日日期|今天星期|今日星期/.test(query);
}

function isWeatherQuestion(query) {
  return /天氣|氣溫|下雨|降雨|天候/.test(query);
}

function isTimeQuestion(query) {
  return /現在幾點|當地時間|當地幾點|時間/.test(query);
}

const LOCATION_ALIASES = [
  { names: ['芳和', '芳和實中', '芳和實驗中學'], city: 'Taipei,Taiwan', zone: 'Asia/Taipei', label: '芳和實中' },
  { names: ['台北', '臺北'], city: 'Taipei,Taiwan', zone: 'Asia/Taipei', label: '台北' },
  { names: ['新北'], city: 'New Taipei,Taiwan', zone: 'Asia/Taipei', label: '新北' },
  { names: ['桃園'], city: 'Taoyuan,Taiwan', zone: 'Asia/Taipei', label: '桃園' },
  { names: ['台中', '臺中'], city: 'Taichung,Taiwan', zone: 'Asia/Taipei', label: '台中' },
  { names: ['台南', '臺南'], city: 'Tainan,Taiwan', zone: 'Asia/Taipei', label: '台南' },
  { names: ['高雄'], city: 'Kaohsiung,Taiwan', zone: 'Asia/Taipei', label: '高雄' },
  { names: ['紐約', 'New York'], city: 'New York,USA', zone: 'America/New_York', label: '紐約' },
  { names: ['洛杉磯', 'Los Angeles'], city: 'Los Angeles,USA', zone: 'America/Los_Angeles', label: '洛杉磯' },
  { names: ['舊金山', '三藩市', 'San Francisco'], city: 'San Francisco,USA', zone: 'America/Los_Angeles', label: '舊金山' },
  { names: ['西雅圖', 'Seattle'], city: 'Seattle,USA', zone: 'America/Los_Angeles', label: '西雅圖' },
  { names: ['芝加哥', 'Chicago'], city: 'Chicago,USA', zone: 'America/Chicago', label: '芝加哥' },
  { names: ['波士頓', 'Boston'], city: 'Boston,USA', zone: 'America/New_York', label: '波士頓' },
  { names: ['華盛頓', 'Washington DC', 'Washington, D.C.'], city: 'Washington,USA', zone: 'America/New_York', label: '華盛頓' },
  { names: ['邁阿密', 'Miami'], city: 'Miami,USA', zone: 'America/New_York', label: '邁阿密' },
  { names: ['東京', 'Tokyo'], city: 'Tokyo,Japan', zone: 'Asia/Tokyo', label: '東京' },
  { names: ['大阪', 'Osaka'], city: 'Osaka,Japan', zone: 'Asia/Tokyo', label: '大阪' },
  { names: ['首爾', 'Seoul'], city: 'Seoul,South Korea', zone: 'Asia/Seoul', label: '首爾' },
  { names: ['新加坡', 'Singapore'], city: 'Singapore', zone: 'Asia/Singapore', label: '新加坡' },
  { names: ['香港', 'Hong Kong'], city: 'Hong Kong', zone: 'Asia/Hong_Kong', label: '香港' },
  { names: ['倫敦', 'London'], city: 'London,UK', zone: 'Europe/London', label: '倫敦' },
  { names: ['雪梨', '悉尼', 'Sydney'], city: 'Sydney,Australia', zone: 'Australia/Sydney', label: '雪梨' },
];

const FOREIGN_REGION = /美國|美利堅|USA|U\.S\.|United States|America|日本|韓國|南韓|Japan|Korea|英國|英格蘭|United Kingdom|英國|加拿大|Canada|澳洲|澳大利亞|Australia|紐西蘭|New Zealand|新加坡|Singapore|香港|Hong Kong|法國|France|德國|Germany|中國|China|泰國|Thailand|越南|Vietnam|馬來西亞|Malaysia/i;

function resolveLocation(query) {
  const found = LOCATION_ALIASES.find(item => item.names.some(name =>
    query.toLowerCase().includes(name.toLowerCase())));
  if (found) return found;
  if (FOREIGN_REGION.test(query)) return null;
  // 校園助理未指定地點時，以芳和實中所在地臺北為預設；不覆蓋明確的國外地點。
  return LOCATION_ALIASES[0];
}

function formatLocalDateTime(zone, now = new Date()) {
  return new Intl.DateTimeFormat('zh-TW', {
    timeZone: zone, year: 'numeric', month: 'long', day: 'numeric',
    weekday: 'long', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(now);
}

function isFastSchoolLookup(query) {
  return /分機|校園電話|行事曆|行事历|行程|請假|行動載具|手機規定|獎懲|品德|生活秩序|法規|規定|主任|組長|職稱|單位|姓名|教師|老師/.test(query);
}

function normalizeCalendarDate(query) {
  // Existing MCP calendar index accepts Chinese dates; normalize YYYY/M/D or M/D.
  return query
    .replace(/(?:20\d{2}[/-])?(\d{1,2})[/-](\d{1,2})/g, '$1月$2日');
}

function unwrapMcpResult(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(unwrapMcpResult).filter(Boolean).join('\n');
  if (typeof value === 'object') {
    if (typeof value.text === 'string') return value.text;
    if (Array.isArray(value.content)) return unwrapMcpResult(value.content);
    if (typeof value.result === 'string') return value.result;
    try { return JSON.stringify(value); } catch { return ''; }
  }
  return String(value);
}

function formatFangheResult(raw) {
  const unwrapped = unwrapMcpResult(raw).trim();
  let data;
  try { data = JSON.parse(unwrapped); } catch { return unwrapped; }
  const lines = [];
  if (data.查詢) lines.push(`查詢：${data.查詢}`);
  if (data.行事曆) {
    for (const week of data.行事曆) {
      lines.push(`行事曆（${week.日期起}～${week.日期迄}）`);
      for (const [office, events] of Object.entries(week.各處室行程 ?? {})) {
        if (events) lines.push(`${office}：\n${events}`);
      }
    }
    if (data.來源) lines.push(`來源：${data.來源}`);
  }
  if (data.法規結果) {
    for (const law of data.法規結果) {
      lines.push(`【${law.文件}】`);
      for (const quote of law.原文摘錄 ?? []) lines.push(`條文摘錄：\n${quote}`);
      if (law.來源) lines.push(`來源：[校方原始文件](${law.來源})`);
    }
  }
  if (data.新增處室法規) {
    for (const law of data.新增處室法規) {
      lines.push(`【${law.處室 ?? ''}${law.標題 ?? ''} ${law.條次或段落 ?? ''}】`);
      if (law.內容) lines.push(law.內容);
      if (law.官方來源) lines.push(`來源：[校方原始文件](${law.官方來源})`);
    }
  }
  for (const key of ['分機總表紀錄', '處室窗口', '班級分機', '年級廣播', '場館分機']) {
    const rows = data[key];
    if (!rows) continue;
    lines.push(`【${key}】`);
    if (Array.isArray(rows)) {
      for (const row of rows) {
        const label = [row.單位, row.職稱, row.姓名, row.大樓, row.場所, row.班級, row.年級]
          .filter(Boolean).join('／');
        const value = row.分機 ?? row.號碼 ?? '';
        lines.push(`• ${label}${value ? `：${Array.isArray(value) ? value.join('、') : value}` : ''}`);
      }
    } else lines.push(JSON.stringify(rows, null, 2));
  }
  if (data.分機資料來源) {
    const src = data.分機資料來源;
    lines.push(`資料來源：${src.文件 ?? ''}${src.公告日期 ? `（${src.公告日期}）` : ''}`);
    if (src.校方網站) lines.push(`來源：[芳和實中校方網站](${src.校方網站})`);
  }
  if (data.法規清單) {
    lines.push('法規／學生手冊資料清單：');
    for (const item of data.法規清單) lines.push(`• [${item.文件}](${item.來源})`);
  }
  if (Array.isArray(data.結果)) {
    for (const item of data.結果) {
      if (!item || typeof item !== 'object') continue;
      if (item.標題) lines.push(`【${item.標題}】`);
      if (item.原文摘錄) lines.push(`原文摘錄：\n${item.原文摘錄}`);
      if (item.官方來源) lines.push(`來源：[芳和實中官方資料](${item.官方來源})`);
    }
  } else if (data.結果) {
    lines.push(String(data.結果));
  }
  if (data.官方首頁) lines.push(`官方首頁：[芳和實中](${data.官方首頁})`);
  if (data.錯誤) lines.push(data.錯誤);
  return lines.length ? lines.join('\n\n') : JSON.stringify(data, null, 2);
}

function getTaiwanDateAndWeekday(now = new Date()) {
  return new Intl.DateTimeFormat('zh-TW', {
    timeZone: TIME_ZONE,
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  }).format(now);
}

/**
 * 回傳快速答案；與日期/星期、天氣無關的問題回傳 null，交給原本 Gemini + MCP 流程。
 * 天氣透過現有 get_weather MCP 工具取得，不新增 MCP server。
 */
export async function getQuickReply(query, mcp, now = new Date()) {
  if (isFastSchoolLookup(query)) {
    const mcpQuery = normalizeCalendarDate(query);
    const raw = await mcp.callTool('search_school_info', { query: mcpQuery });
    return formatFangheResult(raw);
  }

  const asksDate = isDateOrWeekdayQuestion(query);
  const asksWeather = isWeatherQuestion(query);
  const asksTime = isTimeQuestion(query);
  if (!asksDate && !asksWeather && !asksTime) return null;

  const location = resolveLocation(query);
  if (!location && (asksWeather || asksTime)) {
    let examples = '請指定城市名稱';
    if (/美國|美利堅|USA|U\.S\.|United States|America/i.test(query)) examples = '請指定美國城市，例如「紐約」或「洛杉磯」';
    else if (/日本|Japan/i.test(query)) examples = '請指定日本城市，例如「東京」或「大阪」';
    else if (/英國|United Kingdom/i.test(query)) examples = '請指定英國城市，例如「倫敦」';
    return `各城市的天氣與當地時間不同，${examples}。`;
  }

  const tasks = [];
  if (asksDate) tasks.push(Promise.resolve(getTaiwanDateAndWeekday(now)));
  if (asksWeather) {
    tasks.push(mcp.callTool('get_weather', { city: location.city })
      .catch(() => '天氣服務暫時無法連線，請稍後再試。'));
  }
  if (asksTime) tasks.push(Promise.resolve(formatLocalDateTime(location.zone, now)));
  const results = await Promise.all(tasks);
  const parts = [];
  if (asksDate) parts.push(`台灣時間今天是 ${results[0]}。`);
  let index = asksDate ? 1 : 0;
  if (asksWeather) parts.push(`${location.label}天氣：${unwrapMcpResult(results[index++])}`);
  if (asksTime) parts.push(`${location.label}當地時間：${results[index]}。`);
  return parts.join('\n');
}

export { getTaiwanDateAndWeekday };
