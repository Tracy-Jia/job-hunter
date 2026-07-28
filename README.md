# Job Hunter — 不要比谁投得多，比谁不蠢

> *"It is remarkable how much long-term advantage we've gotten by trying to be consistently not stupid, instead of trying to be very intelligent."*

大多数求职工具把"一天投500份"当卖点。这是用发送量替代回复率——跟苏联钢厂按吨位考核一样，你得到了很多吨钢，全是废铁。**HR看到"期待进一步沟通"的第三秒就知道你是海投。**

这个工具每天只处理20-30个岗位。每个都读过JD、做过匹配、招呼语是专门写的。不是因为道德高尚——是因为这么做有效。

扫描 → 筛选 → 读JD → AI匹配 → 生成招呼语 → 发送 → 复盘。基于 [Claude Code](https://claude.com/claude-code)，CDP（Chrome DevTools Protocol）操控本地浏览器。纯本地运行。

## ⚠️ 免责声明

**本项目仅供学习研究使用，严禁用于任何违反第三方平台服务条款（Terms of Service）的行为。**

- 使用者应自行查阅并遵守目标平台的用户协议。自动化操作可能违反平台规定，导致账号被限制、暂停或永久封禁。
- 作者不鼓励、不授权、不承担任何违反第三方平台服务条款的使用行为。使用本项目即表示你自行承担由此产生的一切风险和责任。
- 本项目不隶属于任何招聘平台，亦未获得任何招聘平台的认可或授权。文中提及的平台名称均为其各自所有者的商标。
- 本项目按"现状"提供，不提供任何明示或暗示的担保，包括但不限于适销性、特定用途适用性。作者不对使用本项目产生的任何直接或间接损失承担责任。

## 做什么

| 环节 | 做什么 | 为什么这比大多数方案合理 |
|------|--------|-------------|
| **扫描** | 多关键词批量扫卡片，自动去重 | 把你的求职方向拆成多个搜索词（不同title变体、相邻职能），每个词扫若干条，去重后得到一个不重复的岗位池。拆几个词取决于你的方向有多宽 |
| **筛选** | 排除词 / 薪资底线 / 双休 / 通勤 / 公司黑名单 / 历史已投 / 英语硬要求 | 7层规则。机器做规则判断比人快且一致；人应该做机器做不了的——判断这个岗位值不值得去 |
| **读JD** | CDP逐个打开详情页，绕过字体加密提取明文薪资 | 部分平台把薪资数字用自定义字体加密，普通爬虫只能抓到乱码。我们直接从页面script标签里拿原始数据 |
| **招呼语** | 5段式框架，基于JD逐条定制，按岗位类型切换语气 | 这是整套流水线的护城河。每条招呼语都经过"提取JD需求 → 匹配简历证据 → 选钩子 → 生成 → 质量自检"。不是"您好我对贵司感兴趣" |
| **发送** | redirect-url直连聊天页，MouseEvent触发React handler | 不走API裸调——模拟真实点击，跟手工操作结构上等价 |
| **复盘** | 一个命令扫描聊天列表，告诉你谁回了、谁没回、该跟谁 | 投了不是结束，对方回了才是。第二天自动检测哪些对话有新消息，标注跟进优先级 |

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

六步，每一步有明确的输入和输出。没有"AI智能一键优化"那种废话——你知道每一步在做什么、为什么这么做。

```bash
# ① 快速扫描 — 关键词批量扫卡片。这一步不读JD，只收元数据
python boss_scan.py fast --keywords "人事经理,HRBP,薪酬主管" --city 上海 --count-per-kw 10

# ② 规则预筛 — 7层过滤器。排除词、薪资、双休、通勤、黑名单、历史去重、英语门槛
python boss_prefilter.py --file fast-上海-MMDD-HHMM.json

# ③ 深度读JD — 逐个打开详情页，提取完整JD文本 + 绕过加密拿明文薪资
python boss_scan.py deep --file prefiltered-xxx.json --top 20

# ④ AI生成招呼语 — LLM读JD，按 greeting_guide.md 框架逐条写
#    → 输出 send_list.json（含招呼语 + 匹配点评分）

# ⑤ 发送 — 逐条确认，模拟真实点击
python boss_apply.py -f send_list.json --confirm

# ⑥ 每日复盘 — 自动扫描聊天列表，标注回复状态 + 跟进建议
python boss_daily.py
```

## 招呼语：整套流水线的护城河

5段式框架，详见 `greeting_guide.md`。

```
1. 我的优势 — 一句话亮出最匹配岗位的能力
2. 我做过什么 — 挑一件最拿得出手的经历
3. 结果 — 用数字，别用形容词。不说"有丰富经验"，说"做过300人的薪酬方案"
4. 为什么想来 — 让对方觉得你是认真考虑过这家公司的，不是群发的
5. 结尾 — 自然收尾，根据距离/行业/方向变化。禁用"期待进一步沟通"
```

**硬约束**：80-120字。禁用"贵司""精通""期待进一步沟通"——这些词已经把数百万条招呼语变成了同一条。用具体数字替代形容词。同一批次不同岗位必须用不同切入角度。

**角色语气切换**：同一套框架，不同岗位用不同语气——技术岗侧重成果和硬技能，业务岗侧重业务理解和推动力，管理岗侧重规模和体系搭建。具体规则见 `greeting_guide.md` 的角色差异化表格，使用者根据自己的求职方向自行配置。

## 技术栈

- **DrissionPage 4.x** — CDP连接本地Chrome
- **招聘平台API** — 好友建立 + 聊天页发送
- **React事件兼容** — MouseEvent三件套触发React handler
- **字体加密绕过** — `_jobInfo` script标签提取明文薪资

## 已知限制

**浏览器**：当前在 360 极速浏览器上完成全链路验证。由于 CDP（Chrome DevTools Protocol）是 Chromium 的标准协议，Chrome / Edge / Brave / Opera 等 Chromium 内核浏览器理论上直接兼容——只需将可执行文件路径加入 `config.json` 的 `browser.paths`。Firefox 使用不同的远程调试协议（WebDriver BiDi），暂不支持。

**模型**：招呼语生成环节（工作流第④步）由 LLM 按照 `greeting_guide.md` 中的框架执行——提取 JD 需求 → 匹配简历证据 → 按5段式生成。框架本身是模型无关的，当前使用 Claude（DeepSeek v4）作为执行模型。其他具备中文能力的 LLM（GPT-4 / DeepSeek / Qwen / Gemini 等）均可运行该框架，实际效果取决于模型的中文理解和创意写作能力。

## 文件结构

```
├── boss_scan.py          # 扫描引擎：fast（扫卡片）+ deep（读完整JD）
├── boss_prefilter.py     # 规则预筛：排除词/薪资/双休/通勤/历史去重 + 评分排序
├── boss_apply.py         # 自动发送：属性提取路线，React MouseEvent兼容
├── boss_send.py          # CDP发送备选方案（实验性）
├── boss_daily.py         # 每日摘要：自动检测聊天列表回复状态 + 跟进建议
├── shared.py             # 公共模块：浏览器连接、配置加载、评分、去重
├── test_shared.py        # shared.py 单元测试
│
├── greeting_guide.md     # 招呼语生成规范（5段式框架 + 角色差异化 + 质量自检）
├── SKILL.md              # Claude Code skill 定义（完整六步工作流）
├── config.example.json   # 配置模板（复制为 config.json 使用）
├── resume.example.md     # 简历模板
│
├── 51job_apply.py        # 前程无忧适配（实验性，未经充分验证）
├── liepin_apply.py       # 猎聘适配（实验性，未经充分验证）
├── yupao_apply.py        # 鱼泡直聘适配（实验性，未经充分验证）
│
├── requirements.txt      # Python 依赖
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
