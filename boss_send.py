"""
boss_send.py v4 — 已验证可用
流程：搜岗位→点卡片→点"立即沟通"(.op-btn-chat)→聊天窗开→输入定制语→发送
"""
import json, time, sys
from pathlib import Path
from DrissionPage import ChromiumOptions, ChromiumPage

SKILL_DIR = Path(__file__).parent

def connect_chrome(port=9222):
    opts = ChromiumOptions().set_local_port(port)
    if sys.platform == 'win32':
        for p in [r'D:\360浏览器\360ChromeX\Chrome\Application\360ChromeX.exe']:
            if Path(p).exists():
                opts.set_browser_path(p)
                break
    return ChromiumPage(addr_or_opts=opts)

def send_via_search(page, keyword, city_code, jobs_to_send):
    """
    直接在搜索结果页操作：搜→逐卡片点→发招呼语
    jobs_to_send: [{'company': '...', 'title': '...', 'greeting': '...'}]
    """
    sent = 0
    page.get(f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}")
    time.sleep(5)

    for job in jobs_to_send:
        title = job['title']
        greeting = job['greeting']
        company = job.get('company', '')
        print(f"  📨 {company} | {title}")

        # 1. 点击岗位卡片
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

        # 2. 点击"立即沟通"
        btn = page.ele(".op-btn-chat")
        if not btn:
            print("     ❌ 无沟通按钮")
            continue
        if "is-disabled" in str(btn.attr("class") or ""):
            print("     ⏭ 已沟通")
            continue
        btn.click()
        time.sleep(3)

        # 3. 聊天窗口输入
        div = page.ele("div.chat-input")
        if not div:
            print("     ❌ 无聊天输入框")
            continue
        div.input(greeting)
        time.sleep(1)

        # 4. 点击发送
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

        time.sleep(5)  # 间隔

    return sent


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--file", "-f", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    keyword = data.get("keyword", "人事经理")
    city = data.get("city", "上海")
    jobs = data.get("jobs", [])

    CITY_CODES = {"上海": "101020100", "北京": "101010100", "广州": "101280100",
                  "深圳": "101280600", "杭州": "101210100"}
    city_code = CITY_CODES.get(city, "101020100")

    print(f"📨 {keyword} | {city} | {len(jobs)}条\n")

    if args.dry_run:
        for j in jobs:
            print(f"  [{j['company']}] {j['title']}")
            print(f"  → {j['greeting']}\n")
        return

    page = connect_chrome()
    sent = send_via_search(page, keyword, city_code, jobs)
    print(f"\n✅ 发送: {sent}/{len(jobs)}")

if __name__ == "__main__":
    main()
