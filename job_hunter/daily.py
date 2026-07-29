"""每日复盘：全量扫描建基线 + 增量更新 + 消息原文分析 + 对话智能分类 + 关联 apply-log。"""

import argparse
import json
import time
from pathlib import Path

from .browser import connect_chrome
from .config import load_config

SKILL_DIR = Path(__file__).parent.parent


def load_chat_index() -> dict:
    path = SKILL_DIR / "chat-index.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 2, "conversations": {}, "scan_log": []}


def save_chat_index(index: dict):
    path = SKILL_DIR / "chat-index.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_chat_list(page, max_conversations: int = 60):
    """扫描聊天列表（支持BOSS虚拟滚动），一次性渐进扫描全部可见对话。"""
    conversations = []
    page.get("https://www.zhipin.com/web/geek/chat")
    time.sleep(3)

    processed_names = set()
    same_count = 0

    for scroll_pos in range(0, 30000, 120):
        page.run_js(
            "var c=document.querySelector('.user-list-content');"
            "if(c)c.scrollTop=" + str(scroll_pos) + ";"
        )
        time.sleep(0.6)

        visible = json.loads(page.run_js(
            "return JSON.stringify(Array.from(document.querySelectorAll('.title-box'))"
            ".filter(t=>t.offsetParent).map(t=>t.textContent.trim()).filter(n=>n.length>2));"
        ))

        new_names = [n for n in visible if n and n not in processed_names]
        if not new_names:
            same_count += 1
            if same_count >= 8:
                break
            continue
        same_count = 0

        for name in new_names:
            if len(conversations) >= max_conversations:
                break
            click_ok = json.loads(page.run_js(
                "var target=" + json.dumps(name) + ";"
                "var titles=document.querySelectorAll('.title-box');"
                "for(var t of titles){"
                "if(!t.offsetParent)continue;"
                "if(t.textContent.trim().substring(0,60)===target){"
                "var p=t.closest('[class*=user-item]')||t.parentElement.parentElement;"
                "if(p){p.click();return JSON.stringify({ok:true});}"
                "}"
                "}"
                "return JSON.stringify({ok:false});"
            ))
            if not click_ok.get("ok"):
                continue
            time.sleep(0.8)

            js_state = (
                "return JSON.stringify((function(){"
                "var items=document.querySelectorAll('.message-item');"
                "var myC=0,friendC=0,lastEl=null;"
                "var messages=[];"
                "items.forEach(function(m){"
                "if(!m.offsetParent)return;"
                "lastEl=m;"
                "var isMine=m.classList.contains('item-myself');"
                "if(isMine)myC++;else friendC++;"
                "var textEl=m.querySelector('.message-text,.text,[class*=text]');"
                "var text=textEl?textEl.textContent.trim():m.textContent.trim();"
                "if(text.length>300)text=text.substring(0,300);"
                "messages.push({mine:isMine,text:text});"
                "});"
                "var lastMine=lastEl?lastEl.classList.contains('item-myself'):false;"
                "if(messages.length>8)messages=messages.slice(-8);"
                "return{my:myC,friend:friendC,lastMine:lastMine,messages:messages};"
                "})());"
            )
            msg = json.loads(page.run_js(js_state))
            my_c = msg.get("my", 0)
            friend_c = msg.get("friend", 0)
            last_mine = msg.get("lastMine", False)
            raw_messages = msg.get("messages", [])

            state = classify_state(my_c, friend_c, last_mine, raw_messages)

            conversations.append({
                "name": name,
                "state": state,
                "my_msgs": my_c,
                "friend_msgs": friend_c,
                "last_mine": last_mine,
                "messages": raw_messages,
            })
            processed_names.add(name)

            icon_map = {
                "interview_invite": "[面试]", "rejected": "[拒绝]", "pending": "[待定]",
                "reviewing": "[审核]", "salary_discussion": "[薪资]", "greeted": "[招呼]",
                "boss_replied": "[回复]", "conversation_ended": "[完毕]",
                "default_only": "[默认]", "only_me": "[等]", "boss_replied_no_reply": "[未回]",
                "empty": "[空]",
            }
            icon = icon_map.get(state, "[?]")
            print(f"  [{len(conversations)}] {icon} {name[:40]} (me:{my_c}/boss:{friend_c})")

    return conversations

def classify_state(my_c, friend_c, last_mine, messages):
    friend_texts = [m["text"] for m in messages if not m["mine"]]
    last_friend = friend_texts[-1] if friend_texts else ""

    if friend_c > 0 and friend_texts:
        if any(kw in last_friend for kw in ["面试", "聊聊", "约个时间", "方便过来", "方便来面"]):
            return "interview_invite"
        if any(kw in last_friend for kw in ["不合适", "不符", "已关闭", "已停止", "不考虑", "无缘分"]):
            return "rejected"
        if any(kw in last_friend for kw in ["稍等", "尽快回复", "稍后", "这两天", "下周"]):
            return "pending"
        if any(kw in last_friend for kw in ["简历转", "用人部门", "业务部门", "推进", "筛选"]):
            return "reviewing"
        if any(kw in last_friend for kw in ["薪资", "期望", "待遇", "工资", "薪酬"]):
            return "salary_discussion"
        if my_c > 0 and not last_mine:
            return "boss_replied"
        if my_c > 0 and last_mine:
            return "conversation_ended"
        if my_c <= 1:
            return "boss_replied_no_reply"

    if my_c <= 1 and friend_c == 0:
        return "default_only"
    if my_c > 1 and friend_c == 0:
        return "only_me"
    return "empty"


def merge_scan_into_index(index, fresh, today):
    convs = index.setdefault("conversations", {})
    new_count = 0
    update_count = 0
    for conv in fresh:
        key = conv["name"].strip()
        if not key:
            continue
        if key in convs:
            prev = convs[key]
            changed = (prev.get("latest_state") != conv["state"]
                       or prev.get("my_msgs") != conv["my_msgs"]
                       or prev.get("friend_msgs") != conv["friend_msgs"])
            if changed:
                update_count += 1
            prev["latest_state"] = conv["state"]
            prev["my_msgs"] = conv["my_msgs"]
            prev["friend_msgs"] = conv["friend_msgs"]
            prev["last_scanned"] = today
            prev.setdefault("state_history", []).append({
                "date": today, "state": conv["state"],
                "my_msgs": conv["my_msgs"], "friend_msgs": conv["friend_msgs"],
            })
            if conv.get("messages"):
                prev["last_messages"] = conv["messages"]
        else:
            new_count += 1
            entry = {
                "first_seen": today, "last_scanned": today,
                "latest_state": conv["state"],
                "my_msgs": conv["my_msgs"], "friend_msgs": conv["friend_msgs"],
                "state_history": [{"date": today, "state": conv["state"],
                                   "my_msgs": conv["my_msgs"], "friend_msgs": conv["friend_msgs"]}],
                "matched_send": {"matched": False},
                "is_manual": False, "followup_count": 0, "last_followup_date": None,
                "archived": False, "archive_reason": None,
            }
            if conv.get("messages"):
                entry["last_messages"] = conv["messages"]
            convs[key] = entry

    index["last_scan"] = {"date": today, "total_found": len(fresh),
                           "new": new_count, "updated": update_count}
    index.setdefault("scan_log", []).append({
        "date": today, "new": new_count, "updated": update_count, "total_convs": len(convs),
    })
    return new_count, update_count


def correlate_with_sends(index):
    convs = index.get("conversations", {})
    if not convs:
        return
    applied = []
    for lp in sorted(SKILL_DIR.glob("apply-log-*.json")):
        try:
            log = json.loads(lp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in log.get("sent", []):
            c = (e.get("company") or "").strip().lower()
            if c:
                applied.append((c, e, lp.name))
    for key, entry in convs.items():
        if entry.get("archived"):
            continue
        kl = key.lower().strip()
        for company_lower, record, fname in applied:
            if kl == company_lower or company_lower in kl or kl in company_lower:
                entry["matched_send"] = {
                    "matched": True,
                    "company": record.get("company", ""),
                    "title": record.get("title", ""),
                    "send_time": record.get("send_time", ""),
                    "match_score": record.get("match_score"),
                    "log_file": fname,
                }
                break
        else:
            entry["matched_send"] = {"matched": False}


def print_daily_report(index):
    convs = index.get("conversations", {})
    last_scan = index.get("last_scan", {})
    now = time.strftime("%m-%d %H:%M")

    active = {k: v for k, v in convs.items() if not v.get("archived")}
    archived_count = len(convs) - len(active)

    def g(states):
        return {k: v for k, v in active.items() if v.get("latest_state") in states}

    interview = g(["interview_invite"])
    rejected = g(["rejected"])
    salary = g(["salary_discussion"])
    replied = g(["boss_replied", "greeted"])
    pending_reply = g(["boss_replied_no_reply", "pending"])
    ended = g(["conversation_ended"])
    waiting = g(["default_only", "only_me", "empty"])
    reviewing = g(["reviewing"])

    total_sent = sum(1 for v in active.values()
                     if v.get("matched_send", {}).get("matched") or v.get("is_manual"))

    print(f"\n{'='*50}")
    print(f"每日复盘  {now}")
    print(f"{'='*50}")
    print(f"本次扫描: {last_scan.get('total_found', 0)} 条"
          f"  (+{last_scan.get('new', 0)}新 / ~{last_scan.get('updated', 0)}更新)")
    print(f"活跃投递: {len(active)} 条  (归档: {archived_count})  (bot+手动: {total_sent})")

    print(f"\n-- 需优先处理 --")
    if interview:
        print(f"  [面试邀约] {len(interview)} 条:")
        for k in sorted(interview)[:5]:
            e = interview[k]
            ms = e.get("matched_send", {})
            t = ms.get("title", "?") if ms.get("matched") else "?"
            print(f"    {k[:25]} | {t[:25]} -> 回复确认时间")
    if pending_reply:
        print(f"  [待回复] {len(pending_reply)} 条:")
        for k in sorted(pending_reply)[:5]:
            print(f"    {k[:40]}")
    if rejected:
        print(f"  [被拒] {len(rejected)} 条:")
        for k in sorted(rejected)[:5]:
            print(f"    {k[:40]} -> 建议3天后换角度跟进")

    print(f"\n-- 状态分布 --")
    if interview:   print(f"  面试邀约:     {len(interview)}")
    if reviewing:   print(f"  审核中:       {len(reviewing)}")
    if salary:      print(f"  谈薪资:       {len(salary)}")
    if replied:     print(f"  对方已回复:   {len(replied)}")
    if pending_reply: print(f"  待我回复:   {len(pending_reply)}")
    if ended:       print(f"  沟通完毕:     {len(ended)}")
    if waiting:     print(f"  等待回复:     {len(waiting)}")
    if rejected:    print(f"  被拒:         {len(rejected)} (建议争取)")

    print(f"\n-- 跟进建议 --")
    fc = {k: v for k, v in active.items()
          if v.get("latest_state") in ("default_only", "only_me", "empty")
          and v.get("followup_count", 0) == 0}
    if fc:
        for k in sorted(fc)[:5]:
            print(f"  {k[:30]} | 可跟进 (已发未回)")
    else:
        print(f"  暂无需要跟进的对话")


def main():
    p = argparse.ArgumentParser(description="每日复盘：扫描聊天列表")
    p.add_argument("--init", action="store_true", help="首次全量扫描建基线")
    p.add_argument("--max", type=int, default=0, help="扫描数量")
    p.add_argument("--no-browser", action="store_true", help="不扫描，仅输出报告")
    args = p.parse_args()

    max_scan = args.max or (120 if args.init else 60)
    index = load_chat_index()

    if args.no_browser:
        correlate_with_sends(index)
        print_daily_report(index)
        return

    print(f"[扫描] 最多 {max_scan} 条...")
    try:
        page = connect_chrome(config=load_config(SKILL_DIR))
    except Exception as e:
        print(f"  [失败] 浏览器: {e}")
        return

    fresh = scan_chat_list(page, max_conversations=max_scan)
    today = time.strftime("%Y-%m-%d")
    new_c, upd_c = merge_scan_into_index(index, fresh, today)
    correlate_with_sends(index)
    save_chat_index(index)

    print(f"\n[结果] 新增 {new_c} / 更新 {upd_c} / 共 {len(index['conversations'])} 条")
    print_daily_report(index)
    print(f"\n[存档] chat-index.json 已更新")
