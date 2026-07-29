# Job Hunter — 双向节约HR和求职者的时间，不比谁投得多

> *"It is remarkable how much long-term advantage we've gotten by trying to be consistently not stupid, instead of trying to be very intelligent."*

大多数求职工具把"一天投500份"当卖点。用发送量替代回复率——跟苏联钢厂按吨位考核一样，你得到了很多吨钢，全是废铁。**HR看到"期待进一步沟通"的第三秒就知道你是海投。** 浪费了HR的时间，也浪费了你自己的。

这个工具的逻辑反着来：按关键词广泛扫描 → 规则筛掉明显不合适的 → 对剩下的逐条深度读JD → AI做匹配 → 只给真正适配的岗位生成定制招呼语。最后投递的数量取决于当天搜出来多少合适的——不是设了个上限，是好岗位就那么多。

扫描 → 筛选 → 读JD → AI匹配 → 招呼语 → 发送 → 复盘。基于 [Claude Code](https://claude.com/claude-code)，CDP（Chrome DevTools Protocol）操控本地浏览器。纯本地运行。

> **适用场景**：面向国内招聘市场。核心流水线在一线招聘平台上经过数十轮实战验证，体感最好的平台因合规考虑不在此处具名。

## ⚠️ 免责声明

**本项目仅供学习研究，严禁违反第三方平台服务条款。**

- 自动化操作可能违反平台规定，导致账号受限或封禁——使用前请自行查阅目标平台用户协议。
- 使用本项目即表示你自行承担全部风险和责任，作者不鼓励、不授权任何违规使用。
- 本项目未获得任何招聘平台的认可或授权，提及的平台名称均为其各自所有者的商标。
- 本项目按"现状"提供，不提供任何明示或暗示的担保，作者不对使用产生的任何损失承担责任。

## 做什么

**🔍 扫描** — 多关键词批量扫卡片，自动去重
> 根据求职方向拆成多个搜索词（不同 title 变体、相邻职能），每个词扫若干条，去重后得到一个不重复的岗位池。

**🎯 筛选** — 你的排除规则，系统自动执行
> 想避开什么？保险/教培/外包/单休/远距离/语言不匹配/硬性证书不满足……写进配置一次性筛掉。规则自己做主，机器只负责不遗漏。

**📖 读 JD** — 逐个打开详情页，绕过字体加密提取明文薪资
> 部分平台把薪资数字用自定义字体加密，普通爬虫只能抓到乱码。直接从页面 script 标签里拿原始数据。

**✍️ 招呼语** — 5 段式框架，逐条定制，按岗位类型切换语气
> 整套流水线的护城河。每条招呼语经过「提取 JD 需求 → 匹配简历证据 → 选钩子 → 生成 → 质量自检」。不再是千篇一律的"期待进一步沟通"。

**📨 发送** — redirect-url 直连聊天页，MouseEvent 触发 React handler
> 不走 API 裸调——模拟真实点击，跟手工操作结构上等价。

**📊 复盘** — 一个命令扫描聊天列表，告诉你谁回了、谁没回、该跟谁
> 投了不是结束，对方回了才是。自动检测哪些对话有新消息，标注跟进优先级。

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

### 4. 试试扫描（不投递，放心跑）

```bash
# 30 秒看到第一批结果
python boss.py scan fast --keywords "人事主管" --city 上海 --count-per-kw 5
```

看到 JSON 输出说明一切就绪。接下来可以按下面的工作流正式使用。

## 工作流

六步，每一步有明确的输入和输出。没有"AI智能一键优化"那种废话——你知道每一步在做什么、为什么这么做。

```bash
# ① 快速扫描 — 关键词批量扫卡片。这一步不读JD，只收元数据
python boss.py scan fast --keywords "人事经理,HRBP,薪酬主管" --city 上海 --count-per-kw 10

# ② 规则预筛 — 基于你的 config.json 自动执行。排除词、薪资底线、双休、通勤、黑名单、去重、语言能力、资格证书
python boss.py prefilter --file fast-上海-MMDD-HHMM.json

# ③ 深度读JD — 逐个打开详情页，提取完整JD文本 + 绕过加密拿明文薪资
python boss.py deep --file prefiltered-fast-MMDD-HHMM.json --top 20

# ④ AI生成招呼语 — LLM读JD，按 greeting_guide.md 框架逐条写
#    → 输出 send_list.json（含招呼语 + 匹配点评分）

# ⑤ 发送 — 逐条确认，模拟真实点击
python boss.py apply -f send_list.json --confirm

# ⑥ 每日复盘 — 自动扫描聊天列表，标注回复状态 + 跟进建议
python boss.py daily
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

**📝 示例：某电商公司薪酬主管岗**

输入：JD 要求 200 人以上薪酬核算经验，熟悉个税社保公积金全流程，有薪酬体系搭建经验优先。

输出：
> 3年200+人薪酬核算经验，熟练处理个税、社保、公积金全流程。主导过从0搭建薪酬体系的项目，把原来3天的核算周期压缩到半天。上一家公司年度调薪方案由我独立完成，覆盖12个部门。看过公司的电商业务模式，薪酬复杂度应该不低——这正是我擅长的。附件是我的简历，方便的话可以约个时间聊聊。

## 技术栈

- **DrissionPage 4.x** — CDP（Chrome DevTools Protocol）连接本地Chrome，相当于脚本像真人一样操作你的浏览器，不需要破解任何东西
- **招聘平台API** — 好友建立 + 聊天页发送
- **React事件兼容** — MouseEvent三件套触发React handler
- **字体加密绕过** — `_jobInfo` script标签提取明文薪资

## 已知限制

**浏览器**：当前在 360 极速浏览器上完成全链路验证。由于 CDP（Chrome DevTools Protocol）是 Chromium 的标准协议，Chrome / Edge / Brave / Opera 等 Chromium 内核浏览器理论上直接兼容——只需将可执行文件路径加入 `config.json` 的 `browser.paths`。Firefox 使用不同的远程调试协议（WebDriver BiDi），暂不支持。

**模型**：招呼语生成环节（工作流第④步）由 LLM 按照 `greeting_guide.md` 中的框架执行——提取 JD 需求 → 匹配简历证据 → 按5段式生成。框架本身是模型无关的，当前使用 Claude（DeepSeek v4）作为执行模型。其他具备中文能力的 LLM（GPT-4 / DeepSeek / Qwen / Gemini 等）均可运行该框架，实际效果取决于模型的中文理解和创意写作能力。

## 文件结构

`job_hunter/` → 核心 Python 包（扫描/筛选/发送/招呼语/复盘/浏览器 共 10 个模块）  
`adapters/` → 其他招聘平台适配（实验性）  
`tests/` → 单元测试  
`output/` → 运行时数据（扫描结果、投递日志）

<details>
<summary>📂 展开完整文件树</summary>

```
├── job_hunter/              # 核心 Python 包
│   ├── scanner.py           # 扫描引擎：fast（扫卡片）+ deep（读完整JD）
│   ├── prefilter.py         # 规则预筛：用户自定义排除规则 + 评分排序
│   ├── applier.py           # 自动发送：属性提取路线，React MouseEvent 兼容
│   ├── sender.py            # CDP 搜索页直发方案（备选）
│   ├── greeting.py          # 招呼语生成：5段式框架 + 角色差异化
│   ├── daily.py             # 每日摘要：自动检测聊天列表回复状态 + 跟进建议
│   ├── browser.py           # Chromium 浏览器 CDP 连接
│   ├── config.py            # 用户配置加载
│   ├── scorer.py            # JD 关键词评分 & 去重
│   └── utils.py             # 文本清洗 / 薪资解析 / 日志读写
│
├── adapters/                # 其他平台适配（实验性，仅供参考）
├── tests/                   # 单元测试
├── output/                  # 运行时输出（不入 git）
│   ├── scans/               # fast / deep 扫描结果
│   └── apply-logs/          # 投递日志
│
├── boss.py                   # 单入口 CLI（scan / prefilter / deep / apply / daily）
├── shared.py                # 向后兼容层（旧 import 路径仍可用）
│
├── greeting_guide.md        # 招呼语生成规范
├── SKILL.md                 # Claude Code skill 定义
├── config.example.json      # 配置模板（复制为 config.json 使用）
├── resume.example.md        # 简历模板
├── CHANGELOG.md
│
├── requirements.txt
├── LICENSE
└── README.md
```

</details>

## 常见问题

**Q: 会被封号吗？**

任何自动化操作都有风险。本工具在设计上尽量降低风险——所有操作基于 CDP 操控真实浏览器，与手工操作结构上等价；默认发送间隔 15 秒。但我们无法保证第三方平台的反作弊策略不会升级。**建议用小号先测试，确认稳定后再用主号。**

**Q: 为什么不直接调 API？**

招聘平台的 API 有严格的限流和鉴权机制，且频繁变更。CDP 路线操控真实浏览器，不受 API 限流影响，且反爬检测更难区分"脚本"和"真人"。

**Q: 支持哪些招聘平台？**

核心流水线在一线招聘平台上经过数十轮实战验证（因合规考虑不具名）。`adapters/` 目录下有其他平台的实验性适配器，由社区贡献，稳定性因平台而异。

**Q: 和其他开源求职工具有什么不同？**

大多数工具追求"投得多"——一天几百份，用发送量替代回复率。我们的核心差异在招呼语：不是千篇一律的模板，而是基于目标 JD 逐条定制的 5 段式框架。最终投递数量取决于当天有多少合适的岗位——不是设了个上限，是好岗位就那么多。

## 安全与隐私

- **纯本地运行**：所有操作在你本地浏览器完成，不上传数据到任何第三方
- **真实浏览器操作**：投递动作基于CDP操控真实浏览器，与手工操作等价
- **间隔控制**：默认发送间隔15秒，尊重平台使用限制
- **敏感数据保护**：简历、配置、投递日志已加入 `.gitignore`，不会误传GitHub
- **提交前检查**：`config.json` 和 `resume.md` 已加入 `.gitignore`，首次使用前从 `.example` 文件复制，确认不含个人信息

## 相关工具

job-hunter 是求职工具链中的**投递环节**。另有：

- **简历定制助手**（开发中）—— 根据目标岗位JD反向定制简历，让简历和招呼语从同一套匹配逻辑出发
- **[职业探索助手 career-compass](https://github.com/Tracy-Jia/career-compass)** — 投之前先搞清楚方向。通过故事挖掘和交叉分析帮职业迷茫期的人找到可行路径，可直接导出 job-hunter 配置文件

三个工具互补但不耦合——你可以只用其中一个。

## License

MIT
