# Job Hunter — AI 辅助招聘平台自动投递

> 从扫描→筛选→读JD→生成招呼语→发送，全链路AI辅助。不是海投工具，是帮你把每一份招呼语都写到位。

基于 [Claude Code](https://claude.com/claude-code) 的 skill，通过 CDP (Chrome DevTools Protocol) 操控本地浏览器完成主流招聘平台的自动化投递。

## ⚠️ 免责声明

**本项目仅供学习研究使用。** 使用者应自行评估目标平台的服务条款（Terms of Service, ToS），确保使用方式符合平台规定。自动化操作可能违反部分招聘平台的用户协议，由此产生的账号风险（如限制登录、封禁）由使用者自行承担。作者不鼓励、不承担任何违反第三方平台服务条款的使用行为。

## 核心能力

- **双模式扫描** — `fast` 批量扫卡片 + `deep` 逐页读完整JD
- **规则预筛** — 排除词/薪资底线/双休/通勤/历史去重
- **AI招呼语生成** — 5段式框架，基于JD深度定制，总监级对话语气
- **自动发送** — redirect-url直连聊天页，React MouseEvent兼容
- **每日摘要** — 一个命令看谁回了、谁没回、该跟谁

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动浏览器（需已登录招聘平台）

```bash
# Windows (Chrome)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# 或让脚本自动启动：在 config.json 的 browser.paths 中配置浏览器路径
```

### 3. 准备简历和配置

```bash
cp config.example.json config.json
# 编辑 config.json：填入简历路径、目标岗位、排除词
cp resume.example.md resume.md
# 填入你的简历内容
```

## 工作流

```bash
# ① 快速扫描（多关键词，每个10条）
python boss_scan.py fast --keywords "人事经理,HRBP,薪酬主管" --city 上海 --count-per-kw 10

# ② 规则预筛
python boss_prefilter.py --file fast-上海-MMDD-HHMM.json

# ③ 深度读JD（Top 20）
python boss_scan.py deep --file prefiltered-xxx.json --top 20

# ④ Claude生成招呼语 → 创建 send_list.json

# ⑤ 发送（逐条确认模式）
python boss_apply.py -f send_list.json --confirm

# ⑥ 每日摘要
python boss_daily.py
```

## 招呼语生成规范

5段式框架（详见 `greeting_guide.md`）：

```
1. 我的优势 — 一句话亮出最匹配的能力
2. 我做过什么 — 最拿得出手的经历
3. 结果 — 用数字，别用形容词
4. 为什么想来 — 让对方觉得我是认真考虑过的
5. 结尾 — "很希望能有机会互相深入了解。简历在附件，期待回复。"
```

## 技术栈

- **DrissionPage 4.x** — CDP连接本地Chrome
- **招聘平台API** — 好友建立 + 聊天页发送
- **React事件兼容** — MouseEvent三件套触发React handler
- **字体加密绕过** — `_jobInfo` script标签提取明文薪资

## 文件结构

```
├── boss_scan.py          # 扫描（fast卡片 + deep读JD）
├── boss_prefilter.py     # 规则预筛
├── boss_apply.py         # 自动发送
├── boss_daily.py         # 每日摘要 + 回复检测
├── shared.py             # 公共模块（浏览器连接、配置加载、去重）
├── greeting_guide.md     # 招呼语生成规范
├── SKILL.md             # Claude Code skill定义
├── config.example.json   # 配置模板
├── resume.example.md     # 简历模板
├── requirements.txt      # Python依赖
├── LICENSE               # MIT
└── README.md
```

## 安全与隐私

- **纯本地运行**：所有操作在你本地浏览器完成，不上传数据到任何第三方
- **真实浏览器操作**：投递动作基于CDP操控真实浏览器，与手工操作等价
- **间隔控制**：默认发送间隔15秒，尊重平台使用限制
- **敏感数据保护**：简历、配置、投递日志已加入 `.gitignore`，不会误传GitHub
- **开源前检查**：复制 `config.example.json` → `config.json`，确保不包含个人信息后再提交

## License

MIT
