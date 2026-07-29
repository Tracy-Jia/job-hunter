"""Job Hunter — 单入口 CLI

Usage:
  python boss.py scan fast --keywords "人事经理" --city 上海
  python boss.py prefilter --file fast-xxx.json
  python boss.py deep --file prefiltered-xxx.json --top 20
  python boss.py apply -f send_list.json
  python boss.py daily            每日复盘（扫描+总览日报）
  python boss.py overview         投递管道总览（终端+CSV）
  python boss.py overview mark    标记岗位状态（归档/恢复）
  python boss.py followup         自动跟进发送
  python boss.py followup plan    预览跟进候选
"""

import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent

COMMANDS = {
    "scan":      ("job_hunter.scanner",    "fast + deep 扫描"),
    "prefilter": ("job_hunter.prefilter",  "规则预筛"),
    "deep":      ("job_hunter.scanner",    "深度读JD（scan deep 的别名）"),
    "apply":     ("job_hunter.applier",    "自动发送"),
    "daily":     ("job_hunter.daily",      "每日复盘（扫描+总览日报）"),
    "followup":  ("job_hunter.followup",   "自动跟进发送（未回复对话）"),
    "overview":  ("job_hunter.overview",   "投递管道总览（终端+CSV）"),
    "status":    ("_status",               "查看当前 pipeline 状态"),
}


def _show_status():
    from job_hunter.state import load_state, print_state
    state = load_state(SKILL_DIR)
    print(print_state(state))


def _track_scan_result(args):
    from job_hunter.state import update_state
    mode = getattr(args, 'mode', 'fast')
    if mode == 'fast':
        update_state(SKILL_DIR, phase="scanned",
                     stat_delta={"fast_scanned": 1},
                     next_action="运行 boss.py prefilter --file fast-xxx.json")
    elif mode == 'deep':
        update_state(SKILL_DIR, phase="deep_scanned",
                     stat_delta={"deep_scanned": 1},
                     next_action="Claude 生成招呼语 -> 输出 send_list.json")


def _track_prefilter_result(args):
    from job_hunter.state import update_state
    update_state(SKILL_DIR, phase="prefiltered",
                 next_action="运行 boss.py deep --file prefiltered-xxx.json --top 20")


def _track_apply_result(sent_count):
    from job_hunter.state import update_state
    update_state(SKILL_DIR, phase="sent",
                 stat_delta={"sent": sent_count},
                 next_action="运行 boss.py daily 复盘 或 收工明天继续")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        try:
            _show_status()
            print()
        except Exception:
            pass
        print(__doc__)
        print("子命令:")
        for name, (mod, desc) in COMMANDS.items():
            if name != "status":
                print(f"  {name:<12} {desc}")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        _show_status()
        return

    if cmd == "deep":
        sys.argv[1] = "scan"
        sys.argv.insert(2, "deep")

    # 兼容旧命令
    if cmd == "follow":
        cmd = "followup"

    if cmd not in COMMANDS:
        print(f"未知命令: {cmd}")
        print(f"可用: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    try:
        print("-" * 40)
        _show_status()
        print("-" * 40)
    except Exception:
        pass

    module_name = COMMANDS[cmd][0]
    mod = __import__(module_name, fromlist=["main"])
    sys.argv.pop(1)
    mod.main()

    try:
        if cmd == "scan":
            import argparse
            p = argparse.ArgumentParser()
            p.add_argument("mode", nargs="?", default="fast")
            remaining = [a for a in sys.argv[1:] if not a.startswith("--")]
            mode = remaining[0] if remaining else "fast"
            _track_scan_result(argparse.Namespace(mode=mode))
        elif cmd == "prefilter":
            _track_prefilter_result(None)
        elif cmd == "apply":
            import glob, json
            logs = sorted(glob.glob(str(SKILL_DIR / "apply-log-*.json")))
            if logs:
                with open(logs[-1], "r", encoding="utf-8") as f:
                    log = json.load(f)
                _track_apply_result(len(log.get("sent", [])))
    except Exception:
        pass


if __name__ == "__main__":
    main()
