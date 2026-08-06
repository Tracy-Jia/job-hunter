"""跟进发送：自动向未回复的对话发第2条消息。"""

import argparse
import json
import time
from pathlib import Path

from .browser import connect_chrome
from .config import load_config

SKILL_DIR = Path(__file__).parent.parent


def load_chat_index():
    path = SKILL_DIR / "chat-index.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"conversations": {}}


def save_chat_index(index):
    path = SKILL_DIR / "chat-index.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def find_candidates(index, interval_days=2, max_per_day=10):
    convs = index.get("conversations", {})
    candidates = []
    today = time.strftime("%Y-%m-%d")

    for name, entry in convs.items():
        if entry.get("archived"):
            continue
        if entry.get("friend_msgs", 0) > 0:
            continue
        state = entry.get("latest_state", "")
        if state not in ("default_only", "only_me", "empty"):
            continue
        fc = entry.get("followup_count", 0)
        if fc >= 3:
            continue
        lfd = entry.get("last_followup_date")
        if lfd:
            days_since = (time.mktime(time.strptime(today, "%Y-%m-%d"))
                          - time.mktime(time.strptime(lfd, "%Y-%m-%d"))) / 86400
            if days_since < interval_days:
                continue
        candidates.append((name, entry))

    candidates.sort(key=lambda x: x[1].get("first_seen", ""))
    return candidates[:max_per_day]


def send_followup(page, company_name):
    """用搜索框定位对话→点击→发送跟进消息。

    BOSS聊天列表使用虚拟滚动，旧方法通过遍历 .title-box 无法触达
    历史对话。改为利用聊天页搜索框（.boss-search-input）定位目标。
    """
    page.get("https://www.zhipin.com/web/geek/chat")
    time.sleep(3)

    # Step 1: 搜索目标公司
    search = page.ele(".boss-search-input", timeout=5)
    if not search:
        return False
    search.click()
    time.sleep(0.2)
    page.run_js('document.querySelector(".boss-search-input").select()')
    time.sleep(0.1)
    search.input(company_name)
    time.sleep(2)

    # Step 2: 检查搜索下拉结果
    has_result = page.run_js(
        "return JSON.stringify({"
        "found: !!(document.querySelector('.boss-search-result')"
        " && document.querySelector('.boss-search-result').offsetParent)"
        "})"
    )
    if not json.loads(has_result).get("found"):
        return False

    # Step 3: 点击结果打开对话
    page.run_js('document.querySelector(".boss-search-result").click()')
    time.sleep(2)

    # Step 4: 等待聊天区域就绪
    for _ in range(15):
        ready = page.run_js(
            "return JSON.stringify({ok: !!(document.querySelector('[contenteditable=true]')"
            " && document.querySelector('[contenteditable=true]').offsetParent"
            " && document.querySelector('.btn-send')"
            " && document.querySelector('.btn-send').offsetParent)})"
        )
        if json.loads(ready).get("ok"):
            break
        time.sleep(1)
    else:
        return False

    # Step 5: 输入并发送
    greeting = _build_greeting(company_name)
    page.run_js(
        "var t=arguments[0]; var d=document.querySelector('[contenteditable=true]');"
        "if(d){d.focus(); d.textContent=t;"
        "d.dispatchEvent(new InputEvent('input',{bubbles:true}));}",
        greeting,
    )
    time.sleep(1)
    sent = page.run_js(
        "return (function(){var btn=document.querySelector('.btn-send');"
        "if(!btn) return 'no_btn'; btn.click(); return 'sent';})();"
    )
    time.sleep(1.5)
    return sent == "sent"


def _build_greeting(company_name):
    return (
        "之前和您打过招呼，怕您太忙没看到。"
        "我对贵司这个机会一直挺有意向的，如果有什么需要我补充信息的随时和我说～"
    )


def main():
    p = argparse.ArgumentParser(description="自动跟进发送")
    p.add_argument("cmd", nargs="?", default="", help="'plan' = 仅预览不发送")
    p.add_argument("--interval", type=int, default=2, help="跟进间隔天数")
    p.add_argument("--max", type=int, default=5, help="今日最多跟进条数")
    args = p.parse_args()

    index = load_chat_index()
    candidates = find_candidates(index, args.interval, args.max)

    if not candidates:
        print("[跟进] 暂无需要跟进的对话")
        return

    print(f"[跟进] {len(candidates)} 个候选:\n")
    for name, entry in candidates:
        title = entry.get("matched_send", {}).get("title", "?")
        fc = entry.get("followup_count", 0)
        print(f"  {name[:30]} | {title[:20]} | 已跟{fc}次 | 首见{entry.get('first_seen','')}")

    if args.cmd == "plan":
        print(f"\n[预览] 以上 {len(candidates)} 条可跟进。运行 'followup' 发送。")
        return

    print(f"\n[发送] 开始跟进...")
    try:
        page = connect_chrome(config=load_config(SKILL_DIR))
    except Exception as e:
        print(f"  [失败] 浏览器: {e}")
        return

    results = {"sent": [], "failed": []}
    for name, entry in candidates:
        print(f"  -> {name[:30]}...", end=" ")
        ok = send_followup(page, name)
        if ok:
            print("[OK]")
            results["sent"].append({"company": name, "time": time.strftime("%H:%M:%S")})
            entry["followup_count"] = entry.get("followup_count", 0) + 1
            entry["last_followup_date"] = time.strftime("%Y-%m-%d")
        else:
            print("[FAIL]")
            results["failed"].append({"company": name})
        time.sleep(5)

    save_chat_index(index)
    log_path = SKILL_DIR / f"followup-log-{time.strftime('%m%d-%H%M')}.json"
    log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] {len(results['sent'])} 条 / {len(results['failed'])} 失败")
    print(f"[日志] {log_path}")
