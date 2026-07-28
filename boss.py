"""Job Hunter — 单入口 CLI

Usage:
  python boss.py scan fast --keywords "人事经理" --city 上海
  python boss.py prefilter --file fast-xxx.json
  python boss.py deep --file prefiltered-xxx.json --top 20
  python boss.py apply -f send_list.json
  python boss.py daily
"""
import sys

COMMANDS = {
    "scan":      ("job_hunter.scanner",    "fast + deep 扫描"),
    "prefilter": ("job_hunter.prefilter",  "规则预筛"),
    "deep":      ("job_hunter.scanner",    "深度读JD（scan deep 的别名）"),
    "apply":     ("job_hunter.applier",    "自动发送"),
    "daily":     ("job_hunter.daily",      "每日复盘"),
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("子命令:")
        for name, (mod, desc) in COMMANDS.items():
            print(f"  {name:<12} {desc}")
        sys.exit(0)

    cmd = sys.argv[1]

    # "deep" 是 "scan deep" 的快捷方式
    if cmd == "deep":
        sys.argv[1] = "scan"
        sys.argv.insert(2, "deep")

    if cmd not in COMMANDS:
        print(f"未知命令: {cmd}")
        print(f"可用: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    module_name = COMMANDS[cmd][0]
    mod = __import__(module_name, fromlist=["main"])
    sys.argv.pop(1)  # 去掉子命令名，透传剩余参数
    mod.main()

if __name__ == "__main__":
    main()
