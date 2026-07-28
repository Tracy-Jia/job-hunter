"""发送引擎：详情页 → 提取redirect-url → add API → 聊天页 → 输入+发送。"""

import argparse
import json
import time
from pathlib import Path

from .browser import connect_chrome
from .config import load_config

SKILL_DIR = Path(__file__).parent.parent


def load_sent_links():
    """从历史 apply-log 中聚合已发送链接。"""
    links = set()
    for lp in SKILL_DIR.glob("apply-log-*.json"):
        try:
            with open(lp, "r", encoding="utf-8") as f:
                log = json.load(f)
            for e in log.get("sent", []):
                if e.get("link"):
                    links.add(e["link"].strip())
        except Exception:
            pass
    return links


def send_one(page, job_url, greeting):
    """单岗位发送流程：导航详情页 → 提取redirect-url → JS点击 → 导航聊天页 → 输入 → 发送。"""
    page.get(job_url)
    time.sleep(5)
    page.run_js("window.scrollTo(0, 500)")
    time.sleep(2)

    info = page.run_js('''
return (function() {
    var btn = document.querySelector("a.btn-startchat");
    if (!btn) return JSON.stringify({error: "no_btn"});
    var redirect = btn.getAttribute("redirect-url") || "";
    var dataUrl = btn.getAttribute("data-url") || "";
    btn.click();
    return JSON.stringify({redirect_url: redirect, data_url: dataUrl});
})();
''')
    params = json.loads(info)

    if "error" in params:
        sec_id = page.run_js('''return (function() {
    var ss = document.querySelectorAll("script");
    for (var i = 0; i < ss.length; i++) {
        var c = ss[i].textContent || "";
        if (c.indexOf("_jobInfo") >= 0) {
            var m = c.match(/securityId\\s*:\\s*['\"]([^'\"]+)['\"]/);
            if (m) return m[1];
        }
    }
    return "";
})();''')
        if sec_id:
            add_url = f"/wapi/zpgeek/friend/add.json?securityId={sec_id}"
            page.run_js(
                'var u=arguments[0]; var x=new XMLHttpRequest(); x.open("POST",u,false); '
                'x.setRequestHeader("Content-Type","application/x-www-form-urlencoded"); x.send("");',
                add_url,
            )
            time.sleep(2)
        else:
            return False

    time.sleep(3)

    redirect = params.get("redirect_url", "")
    if not redirect:
        page.get("https://www.zhipin.com/web/geek/chat")
        time.sleep(4)
    else:
        chat_url = "https://www.zhipin.com" + redirect
        page.get(chat_url)
        time.sleep(5)

    ready = page.run_js('''return (function() {
    var d = document.querySelector("[contenteditable=true]");
    var b = document.querySelector(".btn-send");
    return !!(d && d.offsetParent && b && b.offsetParent);
})();''')
    if not ready:
        return False

    page.run_js(
        'var t=arguments[0]; var d=document.querySelector("[contenteditable=true]"); '
        'if(d){d.focus(); d.textContent=t; '
        'd.dispatchEvent(new InputEvent("input",{bubbles:true}));}',
        greeting,
    )
    time.sleep(1.5)

    sent = page.run_js('''return (function() {
    var btn = document.querySelector(".btn-send");
    if (!btn) return "no_btn";
    btn.dispatchEvent(new MouseEvent("mousedown", {bubbles: true, cancelable: true}));
    btn.dispatchEvent(new MouseEvent("mouseup", {bubbles: true, cancelable: true}));
    btn.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true}));
    return "sent";
})();''')
    time.sleep(2)
    return sent == "sent"


def confirm_jobs(valid):
    """交互确认：展示招呼语，用户逐条确认/跳过/编辑。"""
    confirmed = []
    for i, j in enumerate(valid):
        print(f"\n{'─'*50}")
        print(f"[{i+1}/{len(valid)}] {j.get('company','?')} | {j.get('title','?')} | {j.get('match_score','?')}分")
        print(f"薪资: {j.get('salary_clean','?')}")
        print(f"\n招呼语:")
        print(f"  {j.get('greeting','')}")
        print(f"\n[y]发送 [s]跳过 [e]编辑 →", end=" ")
        choice = input().strip().lower()
        if choice in ("y", ""):
            confirmed.append(j)
        elif choice == "e":
            new_g = input("新招呼语: ").strip()
            if new_g:
                j["greeting"] = new_g
                confirmed.append(j)
            else:
                print("  已跳过")
        else:
            print("  已跳过")
    return confirmed


def main():
    p = argparse.ArgumentParser(description="自动投递")
    p.add_argument("--file", "-f", required=True)
    p.add_argument("--top", "-t", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", "-c", action="store_true", help="发送前逐条确认")
    p.add_argument("--interval", type=int, default=15)
    args = p.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "jobs" in data:
        jobs = data["jobs"]
    elif "candidates" in data:
        jobs = data["candidates"]
    else:
        jobs = data if isinstance(data, list) else []
    if args.top > 0:
        jobs = jobs[:args.top]

    valid = [j for j in jobs if j.get("link") and j.get("greeting")]
    sent_links = load_sent_links()

    if args.confirm:
        valid = confirm_jobs(valid)
        if not valid:
            print("没有确认的岗位，退出。")
            return

    print(f"[Apply] {len(valid)} jobs\n")
    if args.dry_run:
        for i, j in enumerate(valid):
            print(f"[{i+1}] {j.get('company','?')} | {j.get('title','?')}")
            print(f"  {j['greeting'][:80]}...\n")
        return

    page = connect_chrome(config=load_config(SKILL_DIR))
    page.get("https://www.zhipin.com/web/geek/job")
    results = {"sent": [], "failed": []}

    for i, job in enumerate(valid):
        company = job.get("company", "?")
        title = job.get("title", "?")
        link = job.get("link", "")
        greeting = job.get("greeting", "")

        print(f"[{i+1}/{len(valid)}] {company} | {title}")

        if link in sent_links:
            print(f"  [SKIP] already sent")
            continue

        ok = send_one(page, link, greeting)
        if ok:
            print(f"  [OK] SENT!")
            results["sent"].append({**job, "send_time": time.strftime("%H:%M:%S")})
            sent_links.add(link)
        else:
            print(f"  [FAIL]")
            results["failed"].append({**job, "reason": "send_failed"})

        if i < len(valid) - 1:
            print(f"  waiting {args.interval}s...")
            time.sleep(args.interval)

    print(f"\n{'='*50}")
    print(f"[DONE] Sent:{len(results['sent'])} Failed:{len(results['failed'])}")

    log_path = SKILL_DIR / f"apply-log-{time.strftime('%m%d-%H%M')}.json"
    log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Log: {log_path}")

    all_sent = {j["link"] for j in results["sent"]}
    if all_sent and args.file:
        full = data.get("jobs", jobs)
        remaining = [j for j in full if j.get("link") not in all_sent]
        if "jobs" in data:
            data["jobs"] = remaining
        with open(args.file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Updated: {len(remaining)} remaining")
