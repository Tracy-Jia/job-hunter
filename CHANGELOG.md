# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `job_hunter/greeting.py` — 招呼语生成模块（原 `build_send_list.py` 入包）
- `output/` 目录 — 运行时数据统一归入 `output/scans/` 和 `output/apply-logs/`

### Changed
- `.gitignore` 更新：移除已入包的脚本引用，增加 `output/` 目录

## [0.2.0] — 2026-07-28

### Added
- **招呼语 5 段式框架** (`greeting_guide.md`)：优势→经历→结果→为什么来→结尾，含角色差异化表格
- **薪资字体加密绕过**：从 `_jobInfo` script 标签提取明文薪资，无需 OCR
- **CDP 发送路线**：redirect-url 直连聊天页 + MouseEvent 三件套触发 React handler
- **每日复盘** (`boss_daily.py`)：自动扫描聊天列表，标注回复状态 + 跟进优先级
- **跨运行去重**：已发送链接持久化，避免同一岗位重复投递
- Chrome 扩展（API 拦截调试用）

### Changed
- **模块化重构**：`boss_*.py` 拆分为 thin CLI 包装器 → `job_hunter/` 包（9 个模块）
- `shared.py` 作为向后兼容 re-export 层保留
- 发送机制从纯 CDP 点击 → API 直连 + CDP 双路线
- 配置文件模板标准化 (`config.example.json`)
- 测试文件归入 `tests/` 目录

### Fixed
- BOSS 直聘详情页 API 参数不匹配导致 JD 读取失败
- 360 极速浏览器 CDP 连接兼容性
- API 搜索限流（每会话 3 次 → 多关键词分批策略）

## [0.1.0] — 2026-07-27

### Added
- 双模式岗位扫描：`fast`（多关键词扫卡片，90 条去重）+ `deep`（逐个导航读完整 JD）
- 7 层可配置预筛选规则（排除词、薪资底线、双休、通勤、黑名单、去重、英语门槛）
- 招呼语生成框架（初版）
- 自动投递发送（CDP 操控浏览器，模拟真实点击）
- 多平台适配器（51job / 猎聘 / 御跑，实验性）
- 纯本地运行，不上传任何数据到第三方
