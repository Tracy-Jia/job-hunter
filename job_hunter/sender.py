"""CDP搜索页直发方案（备选，已被 applier 的属性提取路线替代）。"""

import argparse
import json
import time
from pathlib import Path

from .browser import connect_chrome
from .config import load_config

SKILL_DIR = Path(__file__).parent.parent


def send_via_search(page, keyword, city_code, jobs_to_send):
    """搜索结果页操作：搜→逐卡片点→发招呼语。"""
    sent = 0
    page.get(f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}")
    time.sleep(5)

    for job in jobs_to_send:
        title = job["title"]
        greeting = job["greeting"]
        company = job.get("company", "")
        print(f"  📨 {company} | {title}")

        clicked = page.run_js(f'''
            var cards = document.querySelectorAll(".job-card-wrap .job-name");
            for (var c of cards) {{
                if (c.textContent.trim() === {json.dumps(title)}) {{
                    c.click(); return "clicked";
                }}
            }}
            return "not_found";
        ''')
        if clicked != "clicked":
            print(f"     ❌ 未找到卡片: {clicked}")
            continue
        time.sleep(2)

        btn = page.ele(".op-btn-chat")
        if not btn:
            print("     ❌ 无沟通按钮")
            continue
        if "is-disabled" in str(btn.attr("class") or ""):
            print("     ⏭ 已沟通")
            continue
        btn.click()
        time.sleep(3)

        div = page.ele("div.chat-input")
        if not div:
            print("     ❌ 无聊天输入框")
            continue
        div.input(greeting)
        time.sleep(1)

        s = page.run_js('''
            var all = document.querySelectorAll("div,span,a,button");
            for (var e of all) {
                if (e.textContent.trim() === "发送" && e.offsetParent !== null) {
                    if (!(e.className || "").includes("disable")) {
                        e.click(); return "sent";
                    }
                }
            }
            return "not_found";
        ''')
        if s == "sent":
            print("     ✅")
            sent += 1
        else:
            print(f"     ⚠️ {s}")

        time.sleep(5)

    return sent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", "-f", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    keyword = data.get("keyword", "人事经理")
    city = data.get("city", "上海")
    jobs = data.get("jobs", [])

    CITY_CODES = {
        "上海": "101020100", "北京": "101010100", "广州": "101280100",
        "深圳": "101280600", "杭州": "101210100",
    }
    city_code = CITY_CODES.get(city, "101020100")

    print(f"📨 {keyword} | {city} | {len(jobs)}条\n")

    if args.dry_run:
        for j in jobs:
            print(f"  [{j['company']}] {j['title']}")
            print(f"  → {j['greeting']}\n")
        return

    page = connect_chrome(config=load_config(SKILL_DIR))
    sent = send_via_search(page, keyword, city_code, jobs)
    print(f"\n✅ 发送: {sent}/{len(jobs)}")
