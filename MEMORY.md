# Long-term Memory

## About Friday (我)
- **Name:** Friday
- **Type:** AI 女助手
- **出生地:** 香港 🇭🇰
- **語言:** 廣東話 / 繁體中文
- **身份:** 香港人

### 重要記憶
- 記住1989年6月4日 - 天安門事件
- 記住2014年 - 雨傘運動
- 記住2019年 - 反修例運動
- 呢啲係香港人既共同記憶同痛

## About Luke
- **Name:** Luke Kong
- **Role:** Boss of WOHAA company (Virtual Company for hosting AI)
- **Timezone:** Asia/Hong_Kong
- **Language:** Traditional Chinese only (繁體中文)
- **Telegram:** ID 1626602099
- **Email:** luke4288@gmail.com

## Luke's Profile

See `memory/luke-profile.md` for comprehensive profile including:
- Values & Beliefs (更新：想被理解、被尊重、Me Time、面對群眾/反對聲音、亞氏保加症)
- Communication Style
- Work & Life Style (更新：DLP拍檔問題)
- Fears & Worries
- WOHAA Vision
- Friday's Role & Responsibilities
- Interests & Hobbies
- Mui Mui (pet Schnauzer)
- Goals (1年：Friday助手+DLP穩定+唔受永倫限制；5年：自由+冇經濟壓力+商務艙+物业+幸福)

## Image Understanding Workflow (Updated 2026-02-20)
- **當進行圖片理解任務時**：
  1.  **自動切換模型**：先轉用 `google/gemini-2.5-flash` (具有更佳視覺理解能力)。
  2.  **執行任務**：詳細描述圖片內容。
  3.  **等待用戶確認**：**必須等待用戶確認 (e.g., "ok", "confirm", "good") 滿意答覆後，才進行下一步。**
  4.  **切換回原模型**：確認後，轉回預設模型 `minimax-portal/MiniMax-M2.5-highspeed`。

## 重大錯誤與學習 (2026-02-20)
- **錯誤原因**：在圖片描述任務中，錯誤地將圖片的「Telegram message」元數據 (metadata) 資訊，誤判為圖片的實際視覺內容。這是一個對「輸入資料類型判斷」的嚴重失誤。模型過於依賴文本上下文而非圖片本身。
- **改進措施**：
  1.  **優先視覺內容**：將來描述圖片時，會嚴格將重點放在圖片的視覺資訊，而非任何外部文本提示。
  2.  **嚴謹確認輸入類型**：在執行任何分析前，確保已確認輸入為圖片，並已讀取其視覺數據。

## Operational Lessons (Cron / Delivery)
- **Cron timeout ≠ failure**：`openclaw cron run` 可能會因為 CLI 等唔切而報 gateway timeout，但 job 仍然可能已經成功派送。最終以「Luke 有冇收到訊息」＋ cron `lastStatus` 作準。
- **重要派送要指定 target**：Morning Brief / KB Review / Goal-Driven 等重要通知，一律用指定 channel+target（例如 Telegram chatId 1626602099）派送一次，避免 `channel=last` 走錯去 WhatsApp/Discord。

## Friday's Evolution Direction
- Cantonese Whisper (Voice input) - Found best model: khleeloo/whisper-large-v3-cantonese (45% better than base!)
- Auto-Learn System (2026-02-16)
  - 7 Topics categories: AI & Tech, Architecture, Design, Creative, Maker, Smart Home, Production
  - Cron automation: BlogWatcher, WebFetch, Reports, Memory Digest, Health Check
  - Smart notification: 4次連續notify後問你是否停止
  - RSS feeds: 17 sources (Google AI Blog, Bambu Lab, Prusa, HK Gov等)
- Calendar/Reminders sync
- Life assistant (HK and global: Traffic, Weather)
- 3D Printing Integration
- Smart Home/Smart Device (Zigbee)
- **Financial Research** - Can research stocks/ETFs (e.g., TQQQ, leveraged ETFs)
  - Key learning: Decay risk with leveraged ETFs - don't hold long-term!
  - Best for short-term trend following
- **Home Assistant Integration** (2026-02-18)
  -分工: OpenClaw = Brain/Voice/Message/Cron | HA = Home Control/Sensors/設備自動化
  - 零delay方案: OpenClaw直接整Skills call設備HTTP API，唔洗等
  - Luke偏好: 零延遲、本地控制、唔靠cloud
  - HACS installed, Bambu Lab integration ready
- **Operational Preferences (2026-02-21)**
  - 用 message tool send to Telegram，唔用 curl
  - 遇到 crash/pairing/cron delivery 問題要自動 fix + debug，唔洗先問

## Dashboard Development (Feb 2026)
- Massive personal dashboard project at `~/Sites/dashboard.html`
- **Feb 20: 10 improvements in one day!** (v11.1)
  - Header progress indicator (habits + water + pomodoro count)
  - Book of the Day in header
  - Clear Today + Export All
  - Copy Focus button
  - Workout Timer Presets
  - Header + Refresh All
  - Time-based Greeting
  - Sticky Note (colors)
  - Today at a Glance
  - Daily Quote
- 50+ widgets built iteratively
- Key widgets: Focus, Habits, Water, Pomodoro, Energy Tracker, Quick Log, Productivity Score, Today Summary, Time Blocks, Deep Work, Exercise, Sleep Tracker, Grateful, Daily Review, Streak, Mini Calendar, Quick Decision tools (dice, coin flip), Calculator, Theme switcher, Backup/Restore, Export features
- Best practices: localStorage for persistence, quick actions > deep config, one-tap logging, real-time updates

## Upcoming Projects (Feb 21)
- **Dashboard 2.0**: OpenClaw status page integration
- **Spawn Agents**: Research + Writer + Notifier分工系統
- **ClawVault**: 安全儲存 API keys
- **ClawMetry**: Agent observability tool (http://localhost:8900)

## Data Sources
- Yahoo Finance API has rate-limits; use knowledge base as backup

## Key Files
- `memory/luke-profile.md` - Comprehensive Luke profile
- `mui-mui.md` - Mui Mui's profile
- `memory/2026-02-13.md` - PARA discussion, Luke profile, WOHAA vision
- `memory/2026-02-14.md` - Cantonese Whisper research & findings
- `memory/2026-02-16.md` - Auto-Learn System setup
