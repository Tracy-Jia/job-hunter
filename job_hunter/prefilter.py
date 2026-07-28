"""规则预筛：从 fast scan 中按用户配置筛出值得深度读JD的岗位。"""

import argparse
import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent


def load_config():
    cfg_path = SKILL_DIR / "config.json"
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_applied_companies():
    """从所有 apply-log 中提取已投递的公司名和链接。"""
    applied_companies = set()
    applied_links = set()
    for log_path in SKILL_DIR.glob("apply-log-*.json"):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
            for entry in log.get("sent", []):
                if entry.get("company"):
                    applied_companies.add(entry["company"].strip())
                if entry.get("link"):
                    applied_links.add(entry["link"].strip())
        except Exception:
            pass
    return applied_companies, applied_links


def check_exclude(title, exclude_keywords):
    title_lower = title.lower()
    for kw in exclude_keywords:
        if kw.lower() in title_lower:
            return kw
    return None


def check_company_blacklist(company, blacklist):
    company_lower = company.lower()
    for kw in blacklist:
        if kw.lower() in company_lower:
            return kw
    return None


def check_target_match(title, target_roles):
    title_lower = title.lower()
    return [role for role in target_roles if role.lower() in title_lower]


def analyze_district(district_str):
    near_districts = ["杨浦", "虹口", "宝山", "静安", "闸北", "新江湾"]
    far_districts = ["浦东", "松江", "嘉定", "青浦", "奉贤", "金山", "南汇", "临港", "闵行"]

    district_str = district_str or ""
    for d in near_districts:
        if d in district_str:
            return "near", d
    for d in far_districts:
        if d in district_str:
            return "far", d
    return "mid", ""


def main():
    p = argparse.ArgumentParser(description="预筛fast scan结果")
    p.add_argument("--file", "-f", required=True, help="fast scan输出的JSON文件")
    args = p.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    config = load_config()
    exclude_keywords = config.get("exclude_keywords", [])
    target_roles = config.get("target_roles", [])
    company_blacklist = config.get("company_blacklist", [])
    boost_keywords = config.get("boost_keywords", [])
    schedule_blacklist = config.get("schedule_blacklist", [])
    known_bad = config.get("known_bad_companies", {})
    english_hard = config.get("english_hard_keywords", [])
    english_ok = config.get("english_ok_keywords", [])

    applied_companies, applied_links = load_applied_companies()

    jobs = data.get("jobs", [])
    print(f"[Prefilter] {len(jobs)} 个岗位\n")

    passed = []
    excluded = []
    flagged_far = []

    for job in jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        district = job.get("district", "")
        tags = job.get("tags", [])

        hit = check_exclude(title, exclude_keywords)
        if hit:
            excluded.append({**job, "reason": f"exclude:{hit}"})
            continue

        hit = check_company_blacklist(company, company_blacklist)
        if hit:
            excluded.append({**job, "reason": f"blacklist:{hit}"})
            continue

        if company.strip() in known_bad:
            excluded.append({**job, "reason": f"known_bad:{known_bad[company.strip()]}"})
            continue

        if company.strip() in applied_companies:
            excluded.append({**job, "reason": "already_applied:company"})
            continue
        link = job.get("link", "")
        if link.strip() and link.strip() in applied_links:
            excluded.append({**job, "reason": "already_applied:link"})
            continue

        check_text = title + " " + " ".join(tags)
        schedule_hit = None
        for kw in schedule_blacklist:
            if kw in check_text:
                schedule_hit = kw
                break
        if schedule_hit:
            excluded.append({**job, "reason": f"schedule:{schedule_hit}"})
            continue

        english_hard_hit = None
        english_ok_hit = None
        for kw in english_hard:
            if kw.lower() in check_text.lower():
                english_hard_hit = kw
                break
        if not english_hard_hit:
            for kw in english_ok:
                if kw.lower() in check_text.lower():
                    english_ok_hit = kw
                    break

        target_matches = check_target_match(title, target_roles)
        boost_matches = [k for k in boost_keywords if k.lower() in title.lower()]
        distance, near_dist = analyze_district(district)
        has_weekend = any("双休" in t for t in tags)

        score = 0
        if target_matches:
            score += min(len(target_matches) * 15, 30)
        if boost_matches:
            score += min(len(boost_matches) * 5, 15)
        if has_weekend:
            score += 10
        if distance == "near":
            score += 10
        if english_hard_hit:
            score -= 20
        if english_ok_hit:
            score += 5

        job["_prefilter"] = {
            "score": score,
            "target_matches": target_matches,
            "boost_matches": boost_matches,
            "distance": distance,
            "near_district": near_dist,
            "has_weekend": has_weekend,
            "tags": tags,
            "english_hard": english_hard_hit,
            "english_ok": english_ok_hit,
        }

        if distance == "far":
            flagged_far.append(job)
        else:
            passed.append(job)

    passed.sort(key=lambda j: j["_prefilter"]["score"], reverse=True)

    out = {
        "source": args.file,
        "total_input": len(jobs),
        "passed": len(passed),
        "excluded": len(excluded),
        "flagged_far": len(flagged_far),
        "timestamp": data.get("timestamp", ""),
        "filters_applied": {
            "exclude_keywords": exclude_keywords,
            "company_blacklist": company_blacklist,
            "target_roles": target_roles,
            "schedule_blacklist": schedule_blacklist,
            "applied_companies_dedup": list(applied_companies),
            "known_bad_companies": known_bad,
        },
        "jobs": passed,
        "excluded_jobs": [{**j, "title": j.get("title", ""), "company": j.get("company", ""), "reason": j.get("reason", "")} for j in excluded],
        "far_jobs": flagged_far,
    }

    out_path = SKILL_DIR / f"prefiltered-{Path(args.file).stem}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Result] Passed: {len(passed)} | Excluded: {len(excluded)} | Far: {len(flagged_far)}")
    print(f"[Output] {out_path}")

    print("\n--- Top 15 ---")
    for i, j in enumerate(passed[:15]):
        s = j["_prefilter"]
        company = j["company"][:12]
        title = j["title"][:30]
        salary = j.get("salary_raw", "?")[:15]
        district = j.get("district", "?")[:20]

        def safe(s):
            return s.encode("gbk", errors="replace").decode("gbk", errors="replace")
        line = f"  [{s['score']:2d}] {safe(company)} | {safe(title)} | {safe(salary)} | {safe(district)}"
        print(line)
