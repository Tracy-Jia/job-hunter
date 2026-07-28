"""扫描引擎：fast（扫卡片）+ deep（读完整JD + 提取明文薪资）。"""

import argparse
import json
import re
import time
from pathlib import Path

from .browser import connect_chrome
from .config import load_config
from .utils import clean_text, parse_salary_min


CITY_CODES = {
    "全国": "100010000", "北京": "101010100", "上海": "101020100",
    "广州": "101280100", "深圳": "101280600", "杭州": "101210100",
    "成都": "101270100", "武汉": "101200100", "南京": "101190100",
}

SKILL_DIR = Path(__file__).parent.parent  # repo root


def extract_salary_from_script(page):
    """从 _jobInfo script 标签提取明文薪资（绕过字体加密）。"""
    result = page.run_js('''
return (function() {
    var scripts = document.querySelectorAll("script");
    for (var i = 0; i < scripts.length; i++) {
        var c = scripts[i].textContent || "";
        if (c.indexOf("_jobInfo") >= 0) {
            var salMatch = c.match(/job_salary\\s*:\\s*['"]([^'"]+)['"]/);
            if (salMatch) return salMatch[1];
        }
    }
    return "";
})();
''')
    return result.strip() if result else ""


def search_and_collect(page, keyword, city, city_code, count_per_kw):
    """搜一个关键词，收集卡片元数据（不读JD）。"""
    url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
    page.get(url)
    time.sleep(4)

    cards = []
    seen = set()
    page_num = 1

    while len(cards) < count_per_kw and page_num <= 2:
        time.sleep(1.5)
        card_els = page.eles(".job-card-wrap")
        if not card_els:
            break

        for c in card_els:
            if len(cards) >= count_per_kw:
                break
            try:
                title_el = c.ele(".job-name")
                if not title_el:
                    continue
                title = title_el.text.strip()
                if title in seen:
                    continue
                seen.add(title)

                company_el = c.ele(".boss-name")
                salary_el = c.ele(".job-salary")
                loc_el = c.ele(".company-location")

                cards.append({
                    "title": title,
                    "company": company_el.text.strip() if company_el else "",
                    "salary_raw": salary_el.text.strip() if salary_el else "",
                    "district": loc_el.text.strip() if loc_el else "",
                    "tags": [li.text.strip() for li in c.eles(".tag-list li") if li.text],
                    "link": title_el.attr("href") if title_el else "",
                    "search_keyword": keyword,
                })
            except Exception:
                pass
            time.sleep(0.2)

        if len(cards) < count_per_kw:
            prev = len(page.eles(".job-card-wrap"))
            page.run_js("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            if len(page.eles(".job-card-wrap")) <= prev:
                break
            page_num += 1

    return cards


def parse_commute_km(text):
    """从通勤文本中提取公里数。'距离家庭住址3.2千米' → 3.2"""
    import re
    m = re.search(r"(\d+\.?\d*)\s*(千米|公里|km)", text)
    if m:
        return float(m.group(1))
    return None


def fetch_commute_info(page):
    """从详情页底部提取通勤信息。滚到底 → 搜'距离家庭住址'。"""
    page.run_js("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)
    result = page.run_js('''
return (function() {
    var all = document.querySelectorAll("*");
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        if (!el.offsetParent) continue;
        if (el.children.length > 0) continue;
        var t = (el.textContent || "").trim();
        if (t.indexOf("距离家庭住址") >= 0) return t;
    }
    return "";
})();
''')
    return result.strip() if result else ""


def fetch_jds_for(page, cards, count):
    """逐个打开详情页读取JD + 提取明文薪资 + 提取通勤信息。"""
    for i, card in enumerate(cards[:count]):
        link = card.get("link", "")
        if not link:
            continue
        print(f"  [{i+1}/{min(len(cards), count)}] {card['company']}...", end=" ", flush=True)
        try:
            page.get(link)
            time.sleep(2.5)

            clean_salary = extract_salary_from_script(page)
            if clean_salary:
                card["salary_clean"] = clean_salary
                card["salary_min_k"] = parse_salary_min(clean_salary)

            # 提取通勤信息
            commute = fetch_commute_info(page)
            if commute:
                card["commute"] = commute
                km = parse_commute_km(commute)
                if km is not None:
                    card["commute_km"] = km

            raw = ""
            for sel in [".job-detail-body", ".job-detail-box", ".job-sec-text"]:
                el = page.ele(sel)
                if el and el.text:
                    raw = clean_text(el.text)
                    break
            jd_start = max(raw.find("职位描述"), raw.find("岗位职责"), raw.find("工作内容"), 0)
            card["jd_text"] = clean_text(raw[jd_start:])[:3000] if jd_start > 0 else raw[:3000]
            print(f"{len(card.get('jd_text',''))} chars", end="")
            if clean_salary:
                print(f" | salary={clean_salary} min={card.get('salary_min_k','?')}K", end="")
            if commute:
                print(f" | commute={commute[:30]}", end="")
            print()
        except Exception as e:
            card["jd_text"] = f"[读取失败: {e}]"
            print("FAILED")
        time.sleep(3)
    return cards


# ========== fast 模式 ==========


def cmd_fast(args):
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    city_code = CITY_CODES.get(args.city, "100010000")
    count_per = args.count_per_kw

    print(f"[fast] {len(keywords)}个关键词 | {args.city} | 每个{count_per}条")
    config = load_config(SKILL_DIR)
    page = connect_chrome(config=config)
    page.get("https://www.zhipin.com/web/geek/job")

    page.get(f"https://www.zhipin.com/web/geek/job?query=测试&city={city_code}")
    time.sleep(3)
    if "login" in page.url or "passport" in page.url:
        print("[!] 请登录后按Enter...")
        input()

    all_cards = []
    seen_links = set()

    for i, kw in enumerate(keywords):
        print(f"\n[{i+1}/{len(keywords)}] {kw}")
        cards = search_and_collect(page, kw, args.city, city_code, count_per)
        new = 0
        for c in cards:
            if c["link"] not in seen_links:
                seen_links.add(c["link"])
                all_cards.append(c)
                new += 1
        print(f"  采集{len(cards)}条，去重后{new}条新增 (累计{len(all_cards)}条)")
        time.sleep(3)

    out = SKILL_DIR / f"fast-{args.city}-{time.strftime('%m%d-%H%M')}.json"
    out.write_text(json.dumps({
        "mode": "fast",
        "keywords": keywords,
        "city": args.city,
        "count": len(all_cards),
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "jobs": all_cards
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] {len(all_cards)}条 → {out}")


# ========== deep 模式 ==========


def cmd_deep(args):
    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cards = data.get("jobs", data.get("candidates", []))
    if not cards:
        print("没有岗位数据")
        return

    top_n = min(args.top, len(cards))
    print(f"[deep] 读取Top {top_n}个岗位的JD")

    page = connect_chrome(config=load_config(SKILL_DIR))
    cards = fetch_jds_for(page, cards, top_n)

    out = SKILL_DIR / f"deep-{time.strftime('%m%d-%H%M')}.json"
    out.write_text(json.dumps({
        "mode": "deep",
        "source": args.file,
        "count": top_n,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "jobs": cards[:top_n]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] {out}")


# ========== main ==========


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="mode")

    f = sp.add_parser("fast", help="只扫卡片，不读JD")
    f.add_argument("--keywords", "-k", required=True, help="逗号分隔，如: 人事主管,行政经理,HRBP")
    f.add_argument("--city", "-c", default="上海")
    f.add_argument("--count-per-kw", type=int, default=10, help="每个词采集条数")
    f.set_defaults(func=cmd_fast)

    d = sp.add_parser("deep", help="对fast结果读取JD")
    d.add_argument("--file", "-f", required=True, help="fast输出的JSON文件")
    d.add_argument("--top", "-t", type=int, default=10, help="读Top N个")
    d.set_defaults(func=cmd_deep)

    args = p.parse_args()
    if not args.mode:
        p.print_help()
        return
    args.func(args)
