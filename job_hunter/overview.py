"""投递管道总览：聚合 chat-index + apply-log + manual-sends -> 终端 + CSV。"""

import argparse
import csv
import json
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent


def load_chat_index():
    path = SKILL_DIR / "chat-index.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_manual_sends():
    path = SKILL_DIR / "manual-sends.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def load_config():
    path = SKILL_DIR / "config.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_send_details():
    details = {}
    for lp in sorted(SKILL_DIR.glob("apply-log-*.json")):
        try:
            log = json.loads(lp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in log.get("sent", []):
            c = (e.get("company") or "").strip()
            if c:
                details[c] = {
                    "salary_clean": e.get("salary_clean", ""),
                    "district": e.get("district", ""),
                    "jd_summary": e.get("jd_summary", ""),
                    "match_points": e.get("match_points", []),
                }
    return details


def state_label(state):
    labels = {
        "interview_invite": "面试邀约", "rejected": "被拒(可争取)",
        "pending": "待定", "reviewing": "审核中",
        "salary_discussion": "谈薪资", "greeted": "已回应",
        "boss_replied": "对方已回复", "conversation_ended": "沟通完毕",
        "default_only": "已发未回", "only_me": "已发未回(多条)",
        "boss_replied_no_reply": "待我回复", "empty": "新对话",
    }
    return labels.get(state, state)


def suggest_action(entry):
    state = entry.get("latest_state", "")
    if state == "interview_invite":       return "回复确认时间"
    if state == "rejected":               return "3天后换角度跟进"
    if state == "boss_replied":           return "查看消息并回复"
    if state in ("default_only", "only_me", "empty"):
        if entry.get("followup_count", 0) == 0: return "建议跟进"
        return f"已跟{entry['followup_count']}次"
    if state == "salary_discussion":      return "回复期望薪资"
    if state == "reviewing":              return "等待，3天无消息可跟进"
    if state == "pending":                return "等待对方回复"
    return ""


def build_rows(index, manual_sends, details):
    rows = []
    convs = index.get("conversations", {})
    for name, entry in convs.items():
        ms = entry.get("matched_send", {})
        comp = ms.get("company", "") if ms.get("matched") else name
        d = details.get(comp, {})
        row = {
            "公司": name,
            "岗位": ms.get("title", "") if ms.get("matched") else "",
            "发送日期": ms.get("send_time", ""),
            "发送方式": "手动" if entry.get("is_manual") else ("bot" if ms.get("matched") else "?"),
            "匹配度": ms.get("match_score", ""),
            "薪资": d.get("salary_clean", ""),
            "区域": d.get("district", ""),
            "状态": state_label(entry.get("latest_state", "")),
            "我发数": entry.get("my_msgs", 0),
            "对方回数": entry.get("friend_msgs", 0),
            "跟进次数": entry.get("followup_count", 0),
            "最后活跃": entry.get("last_scanned", ""),
            "归档": "是" if entry.get("archived") else "",
            "建议操作": suggest_action(entry),
        }
        rows.append(row)
    for m in manual_sends:
        rows.append({
            "公司": m.get("company", ""),
            "岗位": m.get("title", ""),
            "发送日期": m.get("sent_date", ""),
            "发送方式": "手动",
            "匹配度": m.get("match_analysis", {}).get("score", ""),
            "薪资": "", "区域": "",
            "状态": "手动投递",
            "我发数": 1, "对方回数": 0, "跟进次数": 0,
            "最后活跃": m.get("added_at", ""),
            "归档": "",
            "建议操作": m.get("match_analysis", {}).get("suggestion", ""),
        })
    return rows


def write_csv(rows, path):
    if not rows:
        return
    fieldnames = ["公司", "岗位", "发送日期", "发送方式", "匹配度", "薪资", "区域",
                  "状态", "我发数", "对方回数", "跟进次数", "最后活跃", "归档", "建议操作"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def print_overview(rows):
    now = time.strftime("%m-%d %H:%M")
    active = [r for r in rows if not r["归档"]]
    archived = [r for r in rows if r["归档"]]

    def count_by_state(part):
        return sum(1 for r in active if part in r["状态"])

    print(f"\n{'='*50}")
    print(f"投递管道总览  {now}")
    print(f"{'='*50}")
    print(f"活跃: {len(active)}条 | 归档: {len(archived)}条")

    urgent = [r for r in active if r["状态"] in ("面试邀约", "对方已回复", "待我回复")]
    can_reject = [r for r in active if r["状态"] == "被拒(可争取)"]
    can_follow = [r for r in active if "建议跟进" in r["建议操作"]]

    print(f"\n-- 需优先处理 --")
    if urgent:
        for r in urgent:
            print(f"  [需回复] {r['公司'][:25]} | {r['岗位'][:20]} | {r['状态']}")
    if can_reject:
        for r in can_reject:
            print(f"  [可争取] {r['公司'][:25]} | {r['岗位'][:20]}")
    if not urgent and not can_reject:
        print(f"  (无紧急事项)")

    print(f"\n-- 状态分布 --")
    for label in ["面试邀约", "审核中", "谈薪资", "对方已回复", "待我回复",
                   "沟通完毕", "已发未回", "被拒(可争取)", "已回应", "待定"]:
        c = count_by_state(label)
        if c:
            print(f"  {label}: {c}")

    if can_follow:
        print(f"\n-- 可跟进 ({len(can_follow)}条) --")
        for r in can_follow[:8]:
            print(f"  {r['公司'][:25]} | {r['岗位'][:20]}")

    if archived:
        print(f"\n-- 归档 (--show-archived 查看) -- {len(archived)}条")


def analyze_match(company_name, title_hint=""):
    cfg = load_config()
    target_roles = cfg.get("target_roles", [])
    exclude_keywords = cfg.get("exclude_keywords", [])
    boost_keywords = cfg.get("boost_keywords", [])
    check_text = (company_name + " " + title_hint).lower()
    score = 50
    target_hits = [r for r in target_roles if r.lower() in check_text]
    exclude_hits = [k for k in exclude_keywords if k.lower() in check_text]
    boost_hits = [k for k in boost_keywords if k.lower() in check_text]
    score += len(target_hits) * 15
    score -= len(exclude_hits) * 20
    score += len(boost_hits) * 10
    score = max(0, min(100, score))
    
    parts = []
    if target_hits: parts.append(f"匹配目标岗位: {', '.join(target_hits)}")
    if exclude_hits: parts.append(f"注意排除词: {', '.join(exclude_hits)}")
    if boost_hits: parts.append(f"加分项: {', '.join(boost_hits)}")
    
    suggestion = f"匹配度{score}分"
    if score >= 70: suggestion += "，建议2天后跟进"
    elif score >= 50: suggestion += "，可争取"
    else: suggestion += "，可考虑归档"
    
    return {"score": score, "target_hits": target_hits,
            "exclude_hits": exclude_hits, "boost_hits": boost_hits,
            "suggestion": suggestion}


def cmd_mark(args):
    index = load_chat_index()
    convs = index.get("conversations", {})
    name = args.company
    if name not in convs:
        matches = [k for k in convs if name.lower() in k.lower()]
        if len(matches) == 1:
            name = matches[0]
        elif len(matches) > 1:
            print(f"匹配到多个: {matches}"); return
        else:
            print(f"未找到: {name}"); return
    entry = convs[name]
    if args.unarchive:
        entry["archived"] = False; entry["archive_reason"] = None
        print(f"[OK] {name} 已恢复")
    elif args.reject:
        entry["archived"] = True; entry["archive_reason"] = "rejected"
        print(f"[OK] {name} 已标记为拒绝/不合适")
    elif args.junk:
        entry["archived"] = True; entry["archive_reason"] = "junk"
        print(f"[OK] {name} 已归档 (垃圾岗位)")
    path = SKILL_DIR / "chat-index.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")



def cmd_scan_manual(args):
    """自动扫描未关联对话，批量录入手动投递。"""
    index = load_chat_index()
    convs = index.get("conversations", {})
    manual = load_manual_sends()
    already = {m.get("company", "").strip().lower() for m in manual}
    cfg = load_config()
    target_roles = cfg.get("target_roles", [])

    candidates = []
    for name, entry in convs.items():
        if entry.get("archived"): continue
        if entry.get("is_manual"): continue
        if name.strip().lower() in already: continue
        if entry.get("matched_send", {}).get("matched"): continue
        candidates.append((name, entry))

    if not candidates:
        print("[scan-manual] 没有未关联的对话")
        return

    saved = 0
    for name, entry in candidates:
        # 从对话名中自动提取岗位名：匹配 target_roles 中的关键词
        title = ""
        for role in target_roles:
            if role.lower() in name.lower():
                title = role
                break

        analysis = analyze_match(name, title)

        manual.append({
            "company": name, "title": title, "link": "",
            "sent_date": entry.get("first_seen", ""),
            "greeting": "手动投递（系统默认招呼语）",
            "added_at": time.strftime("%Y-%m-%d %H:%M"),
            "match_analysis": analysis,
        })
        entry["is_manual"] = True
        entry["matched_send"] = {
            "matched": True, "company": name, "title": title,
            "match_score": analysis["score"], "log_file": "manual",
        }
        saved += 1

        title_display = f" | {title}" if title else ""
        print(f"  [OK] {name[:35]}{title_display} | {analysis['suggestion']}")

    man_path = SKILL_DIR / "manual-sends.json"
    man_path.write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
    idx_path = SKILL_DIR / "chat-index.json"
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] 自动录入 {saved}/{len(candidates)} 条 -> manual-sends.json + chat-index.json")

def main():
    p = argparse.ArgumentParser(description="投递管道总览")
    sub = p.add_subparsers(dest="cmd")

    mark = sub.add_parser("mark", help="标记岗位状态")
    mark.add_argument("company", help="公司名")
    mark.add_argument("--reject", action="store_true", help="标记为拒绝/不合适")
    mark.add_argument("--junk", action="store_true", help="标记为垃圾岗位")
    mark.add_argument("--unarchive", action="store_true", help="恢复")

    sub.add_parser("scan-manual", help="扫描未关联对话并录入手动投递")

    p.add_argument("--csv-only", action="store_true", help="只输出CSV")
    p.add_argument("--show-archived", action="store_true", help="包含归档条目")
    p.add_argument("--csv-path", type=str, default="", help="CSV输出路径")

    args = p.parse_args()

    if hasattr(args, "cmd"):
        if args.cmd == "mark":
            cmd_mark(args); return
        if args.cmd == "scan-manual":
            cmd_scan_manual(args); return

    index = load_chat_index()
    manual = load_manual_sends()
    details = load_send_details()
    rows = build_rows(index, manual, details)

    if not args.show_archived:
        rows = [r for r in rows if not r["归档"]]

    csv_path = args.csv_path or str(SKILL_DIR / f"overview-{time.strftime('%m%d-%H%M')}.csv")
    write_csv(rows, csv_path)
    print(f"[CSV] {csv_path}")

    if not args.csv_only:
        print_overview(rows)


