---
name: job-hunter
description: 求职自动投递助手。读取用户简历与偏好，在招聘平台批量按匹配度投递。触发词：投简历、自动投递、找工作、job-hunter、帮我投递
origin: local
---

# Job Hunter — 自动求职投递

## Deep-First 工作流（标准流程）

```
① fast scan    ② prefilter    ③ deep scan     ④ AI匹配+招呼语   ⑤ apply
  boss_scan.py   boss_prefilter  boss_scan.py    Claude分析        boss_apply.py
  12关键词/批     规则筛          读JD            按规范生成         自动发送
  ~3分钟          ~1秒            ~2分钟/个        招呼语            ~10秒/个
```

**核心原则：没有 JD 文本，不生成招呼语。** 招呼语生成严格遵循 `greeting_guide.md`。

---

## 完整交互流程（Claude 执行步骤）

### Step 0：检查配置

读取 `config.json`。文件不存在 → Step 1；存在 → Step 2。

### Step 1：首次引导（生成 config.json）

引导用户提供：简历路径、期望岗位方向、排除关键词。

从简历中抽取技能关键词，生成 config.json（格式见文件末尾）。

### Step 2：收集本次投递关键词

问用户：

> 今天搜索哪些关键词？（默认12个，逗号分隔）
> 如：人事经理, HRBP, 薪酬绩效主管, 办公室主任, 总经理助理, 行政经理

用户也可以说"用上次的"或"默认"。

### Step 3：确认浏览器已启动

启动时需加 `--remote-debugging-port=9222` 参数（端口号与 config.json 中 browser.port 一致）。脚本也会自动尝试启动——若已手动启动则直接连接。

已登录招聘平台 → 继续。

### Step 4：fast scan（全量扫卡片）

```bash
cd ~/.claude/skills/job-hunter
python boss_scan.py fast --keywords "人事经理,HRBP,薪酬主管,..." --city 上海 --count-per-kw 10
```

输出：`fast-上海-MMDD-HHMM.json`

### Step 5：prefilter（规则预筛）

```bash
python boss_prefilter.py --file fast-上海-MMDD-HHMM.json
```

输出：`prefiltered-fast-上海-MMDD-HHMM.json`

自动过滤：排除词、公司黑名单。按目标岗位匹配度评分排序。标记远距离区域。

### Step 6：Claude 审核预筛结果

读取 prefiltered 结果，向用户展示：

- Top N（按评分排序）
- 标记了"远距离"的岗位
- 评分低于阈值的

用户确认后，决定 deep scan 的 Top N。

### Step 7：deep scan（读JD）

```bash
python boss_scan.py deep --file prefiltered-xxx.json --top 20
```

输出：`deep-MMDD-HHMM.json`（含完整 JD 文本）

### Step 8：Claude JD匹配 + 招呼语生成

对每条 deep scan 结果：

1. 读取 JD 文本
2. 按 `greeting_guide.md` 执行 Step 1-4（提取需求 → 匹配映射 → 选钩子 → 生成招呼语）
3. 按质量自检清单逐条检查
4. 低于60分匹配度的标记为"不建议投递"

输出：`send_list.json`，格式：

```json
{
  "keyword": "人事经理",
  "city": "上海",
  "generated_at": "2026-07-28 10:30",
  "jobs": [
    {
      "company": "公司名",
      "title": "岗位名",
      "link": "详情页URL",
      "greeting": "生成的招呼语",
      "match_score": 85,
      "match_points": ["匹配点1", "匹配点2"],
      "jd_summary": "JD一句话总结"
    }
  ]
}
```

### Step 9：用户确认

展示 send_list 摘要，用户确认或微调后进入发送。

### Step 10：自动发送

```bash
# 先预览
python boss_apply.py --file send_list.json --dry-run

# 正式发送
python boss_apply.py --file send_list.json --interval 10
```

间隔建议 10 秒（模拟人工）。

### Step 11：报告结果

发送日志 `apply-log-MMDD-HHMM.json`。统计：发送成功/跳过/失败。

---

## 发送原理（boss_apply.py v2）

基于详情页属性提取，不依赖 SPA 按钮点击：

```
详情页 → 提取 a.btn-startchat 的 data-url + redirect-url
      → POST data-url (add.json API) 建立好友连接
      → 导航到 redirect-url (聊天页面)
      → 输入招呼语到 [contenteditable=true]
      → 点击 .btn-send 发送
```

**注意**：add.json 会触发 BOSS 自动发送默认招呼语。我们的定制招呼语是第2条消息。详见 `greeting_guide.md` 的"重要前置知识"。

---

## 技术栈

- **DrissionPage 4.x** — CDP 连接本地 Chrome（端口 9222）
- **boss_scan.py** — fast（扫卡片）/ deep（读JD）双模式
- **boss_prefilter.py** — 规则预筛（排除词、黑名单、目标匹配、评分）
- **boss_apply.py v2** — 属性提取 + add API + 聊天页发送
- **greeting_guide.md** — 招呼语生成规范

## 文件结构

```
~/.claude/skills/job-hunter/
├── SKILL.md                   # 本文件
├── greeting_guide.md          # 招呼语生成规范
├── README.md
├── CHANGELOG.md
├── job_hunter/                # 核心 Python 包（实现代码）
│   ├── scanner.py
│   ├── prefilter.py
│   ├── applier.py
│   └── ...
├── boss_scan.py               # CLI 入口（thin wrapper）
├── boss_prefilter.py          # CLI 入口
├── boss_apply.py              # CLI 入口
├── boss_daily.py              # CLI 入口
├── shared.py                  # 向后兼容层
├── adapters/                  # 其他平台适配（实验性）
├── tests/                     # 单元测试
├── config.json                # 用户配置（gitignore）
├── config.example.json        # 配置模板
├── resume.md                  # 用户简历（gitignore）
├── fast-*.json                # fast scan 输出
├── prefiltered-*.json         # prefilter 输出
├── deep-*.json                # deep scan 输出（含JD）
├── send_list.json             # 最终投递清单
└── apply-log-*.json           # 发送日志
```

## 跨运行去重

发送日志 `apply-log-*.json` 记录已投岗位的 link。`boss_apply.py` 发送前自动排除已投过的 link。

## BOSS 反爬注意事项

- 关键词间隔 ≥ 3 秒
- 详情页访问间隔 ≥ 3 秒
- 发送间隔 ≥ 8 秒（建议 10 秒）
- 每日投递总量建议 ≤ 30
- 上午 10:00-11:30 是 HR 活跃窗口，投递效果最好
