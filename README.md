# Job Hunter — 让每一条招呼语都像人写的

> 市面上的投递工具都在比"谁发得多"。这个是反过来的——每天只投20-30个，但每一个岗位的招呼语都读过JD、做过匹配、针对性地写。
>
> 全链路：扫描 → 筛选 → 读JD → AI匹配 → 生成招呼语 → 自动发送 → 每日复盘。

**核心理念：HR一眼能看出你是不是海投。** 招呼语是你给HR的第一印象，也是大多数求职者最敷衍的一环。这个工具用 AI 把 JD 关键需求拎出来，从你的简历里找最匹配的证据，生成一条读起来"这个人认真看过我们岗位"的消息。

基于 [Claude Code](https://claude.com/claude-code) 的 skill，通过 CDP (Chrome DevTools Protocol) 操控本地浏览器完成主流招聘平台的自动化投递。**纯本地运行，不上传任何数据到第三方。**

## ⚠️ 免责声明

**本项目仅供学习研究使用。** 使用者应自行评估目标平台的服务条款（Terms of Service, ToS），确保使用方式符合平台规定。自动化操作可能违反部分招聘平台的用户协议，由此产生的账号风险（如限制登录、封禁）由使用者自行承担。作者不鼓励、不承担任何违反第三方平台服务条款的使用行为。

## 核心能力

| 环节 | 做什么 | 为什么不一样 |
|------|--------|-------------|
| **扫描** | 多关键词批量扫卡片，自动去重 | 每个词搜10条，12个词就是120条去重后~90条，3分钟完成 |
| **筛选** | 排除词/薪资底线/双休/通勤/公司黑名单/历史已投/英语口语硬要求 | 7层规则自动筛，不用人肉看 |
| **读JD** | CDP逐个打开详情页，绕过字体加密提取明文薪资 | 部分平台的薪资使用字体加密，普通爬虫拿不到真实数字 |
| **招呼语** | 5段式框架，基于JD深度定制，角色差异化语气 | 每条都是读过JD后写的，不是模板填空 |
| **发送** | redirect-url直连聊天页，React MouseEvent兼容 | 模拟真实点击而非API裸调，更安全 |
| **复盘** | 一个命令自动扫描聊天列表，告诉你谁回了、谁没回、该跟谁 | 投完不是终点，回复了才是 |

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
1. 我的优势 — 一句话亮出最匹配岗位的能力
2. 我做过什么 — 挑一件最拿得出手的经历
3. 结果 — 用数字，别用形容词
4. 为什么想来 — 让对方觉得我是认真考虑过的
5. 结尾 — 自然收尾，不套模板，根据距离/行业/方向灵活变化
```

**约束**：80-120字、禁用"贵司""精通""期待进一步沟通"等模板词、用具体数字替代形容词、同一批次不同岗位必须差异化切入。

**角色语气**：薪酬绩效岗专业硬核、HRBP用业务视角、总助/办主任干练执行力、HR全盘全面不泛。

## 技术栈

- **DrissionPage 4.x** — CDP连接本地Chrome
- **招聘平台API** — 好友建立 + 聊天页发送
- **React事件兼容** — MouseEvent三件套触发React handler
- **字体加密绕过** — `_jobInfo` script标签提取明文薪资

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
├── 51job_apply.py        # 前程无忧适配
├── liepin_apply.py       # 猎聘适配
├── yupao_apply.py        # 鱼泡直聘适配
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
