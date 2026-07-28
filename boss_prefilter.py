"""
boss_prefilter.py — 规则预筛，从fast scan结果中筛选值得deep读的岗位
用法: python boss_prefilter.py --file fast-上海-xxx.json

筛选规则（从config.json读取）:
  1. 排除词命中 → 直接跳过
  2. 公司黑名单命中 → 跳过
  3. 目标岗位命中 → 加分
  4. 薪资检查 → 标记（BOSS字体加密，无法自动解析，标记为manual_review）
  5. 区域分析 → 标记远距离区域

输出: prefiltered-xxx.json，含筛选结果 + 统计
"""
import json, re, sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent

def load_config():
    cfg_path = SKILL_DIR / "config.json"
    if cfg_path.exists():
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_applied_companies():
    """从所有apply-log中提取已投递的公司名和链接"""
    applied_companies = set()
    applied_links = set()
    for log_path in SKILL_DIR.glob("apply-log-*.json"):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
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
    """检查标题是否命中排除词"""
    title_lower = title.lower()
    for kw in exclude_keywords:
        if kw.lower() in title_lower:
            return kw
    return None

def check_company_blacklist(company, blacklist):
    """检查公司名是否命中黑名单"""
    company_lower = company.lower()
    for kw in blacklist:
        if kw.lower() in company_lower:
            return kw
    return None

def check_target_match(title, target_roles):
    """检查标题是否命中目标岗位"""
    title_lower = title.lower()
    matches = []
    for role in target_roles:
        if role.lower() in title_lower:
            matches.append(role)
    return matches

def analyze_district(district_str):
    """分析区域，标记远距离区域"""
    # 江湾镇/上海财经大学附近 → 杨浦/虹口/宝山(近) 优先
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

def estimate_salary_range(salary_raw):
    """尝试从乱码薪资字符串估算范围（BOSS字体加密，只能做启发式）"""
    if not salary_raw:
        return None, None
    # 尝试提取K前面的数字模式
    # BOSS薪资格式通常是 "XX-XXK" 或 "XX-XXK·XX薪"
    # 但由于字体加密，数字被替换为特殊字符，无法可靠解析
    # 这里只做标记，由Claude人工审核
    text = salary_raw
    # 检查是否有"K"（千）标记
    has_k = "K" in text.upper() or "k" in text
    # 检查大概长度（短=低薪，长=高薪或多数字）
    digit_chars = len([c for c in text if c.isdigit() or ord(c) > 127])
    return has_k, digit_chars


def main():
    import argparse
    p = argparse.ArgumentParser(description="预筛fast scan结果")
    p.add_argument("--file", "-f", required=True, help="fast scan输出的JSON文件")
    p.add_argument("--min-salary-hint", type=int, default=0, help="最低薪资标记（默认0=不按薪资过滤，只标记）")
    args = p.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
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

    # 加载历史投递记录用于去重
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
        salary_raw = job.get("salary_raw", "")
        tags = job.get("tags", [])

        # 1. 排除词检查
        hit = check_exclude(title, exclude_keywords)
        if hit:
            excluded.append({**job, "reason": f"exclude:{hit}"})
            continue

        # 2. 公司黑名单
        hit = check_company_blacklist(company, company_blacklist)
        if hit:
            excluded.append({**job, "reason": f"blacklist:{hit}"})
            continue

        # 2b. 已知烂公司（从历史投递中验证）
        if company.strip() in known_bad:
            excluded.append({**job, "reason": f"known_bad:{known_bad[company.strip()]}"})
            continue

        # 2c. 历史投递去重（公司名或链接已投过）
        if company.strip() in applied_companies:
            excluded.append({**job, "reason": "already_applied:company"})
            continue
        link = job.get("link", "")
        if link.strip() and link.strip() in applied_links:
            excluded.append({**job, "reason": "already_applied:link"})
            continue

        # 2d. 大小周/单休检测（标题+标签）
        schedule_hit = None
        check_text = title + " " + " ".join(tags)
        for kw in schedule_blacklist:
            if kw in check_text:
                schedule_hit = kw
                break
        if schedule_hit:
            excluded.append({**job, "reason": f"schedule:{schedule_hit}"})
            continue

        # 2e. 英语口语硬要求检测（标题+标签，不自动排除但标记扣分）
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

        # 3. 目标岗位匹配
        target_matches = check_target_match(title, target_roles)
        boost_matches = [k for k in boost_keywords if k.lower() in title.lower()]

        # 4. 区域分析
        distance, near_dist = analyze_district(district)

        # 5. 标签分析
        has_weekend = any("双休" in t for t in tags)

        # 评分
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
            score -= 20  # 英语口语硬要求，大幅扣分
        if english_ok_hit:
            score += 5   # 只要求基础英语，轻微加分

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

    # 按评分排序
    passed.sort(key=lambda j: j["_prefilter"]["score"], reverse=True)

    # 输出
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
        "excluded_jobs": [{**j, "title": j.get("title",""), "company": j.get("company",""), "reason": j.get("reason","")} for j in excluded],
        "far_jobs": flagged_far,  # 远距离但仍然保留，供Claude审核
    }

    out_path = SKILL_DIR / f"prefiltered-{Path(args.file).stem}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[Result] Passed: {len(passed)} | Excluded: {len(excluded)} | Far: {len(flagged_far)}")
    print(f"[Output] {out_path}")

    # 简要列表（处理GBK编码异常的BOSS字体字符）
    print("\n--- Top 15 ---")
    for i, j in enumerate(passed[:15]):
        s = j["_prefilter"]
        company = j['company'][:12]
        title = j['title'][:30]
        salary = j.get('salary_raw','?')[:15]
        district = j.get('district','?')[:20]
        # 过滤掉GBK无法编码的字符（BOSS字体加密字符）
        def safe(s):
            return s.encode('gbk', errors='replace').decode('gbk', errors='replace')
        line = f"  [{s['score']:2d}] {safe(company)} | {safe(title)} | {safe(salary)} | {safe(district)}"
        print(line)


if __name__ == "__main__":
    main()
