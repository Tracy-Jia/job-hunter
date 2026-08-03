"""扫描引擎：fast（扫卡片）+ deep（读完整JD + 提取明文薪资）。"""

import argparse
import json
import re
import time
from pathlib import Path

from .browser import connect_chrome
from .config import load_config
from .utils import clean_text, decode_boss_salary, parse_salary_min, calculate_commute


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

                salary_raw = salary_el.text.strip() if salary_el else ""
                salary_decoded = decode_boss_salary(salary_raw)
                salary_min = parse_salary_min(salary_decoded)

                cards.append({
                    "title": title,
                    "company": company_el.text.strip() if company_el else "",
                    "salary_raw": salary_raw,
                    "salary_decoded": salary_decoded,
                    "salary_min_k": salary_min,
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


def fetch_company_info(page):
    """从详情页右侧提取公司基本信息：规模/行业/注册资本/融资阶段。"""
    result = page.run_js('''
return (function() {
    // 先找公司信息容器
    var containers = [];
    var sel = document.querySelector(".company-info-box");
    if (sel) containers.push(sel);
    sel = document.querySelector(".biz-card");
    if (sel) containers.push(sel);
    // 如果找不到，遍历所有匹配公司关键字的元素
    var all = document.querySelectorAll("[class*=company], [class*=biz]");
    for (var i = 0; i < all.length; i++) {
        var t = (all[i].textContent || "").trim();
        if (t.indexOf("注册资本") >= 0 || t.indexOf("公司规模") >= 0) {
            containers.push(all[i]);
            break;
        }
    }
    if (containers.length === 0) return "";
    return containers[0].textContent.trim().substring(0, 500);
})();
''')
    if not result:
        return {}

    info = {}
    # 公司规模
    m = re.search(r"公司规模[：:]\s*(.+?)(?:\n|$)", result)
    if m: info["scale"] = m.group(1).strip()
    # 行业
    m = re.search(r"(?:行业|所属行业)[：:]\s*(.+?)(?:\n|$)", result)
    if m: info["industry"] = m.group(1).strip()
    # 注册资本
    m = re.search(r"注册资本[：:]\s*(.+?)(?:\n|$)", result)
    if m:
        cap = m.group(1).strip()
        info["registered_capital"] = cap
        # 提取数字用于过滤
        num_m = re.search(r"(\d+\.?\d*)\s*(万|亿元)?", cap)
        if num_m:
            amount = float(num_m.group(1))
            unit = num_m.group(2) if num_m.group(2) else "万"
            if unit == "亿元":
                amount *= 10000  # 转成万
            info["registered_capital_wan"] = amount
    # 融资阶段
    m = re.search(r"(?:融资阶段|融资)[：:]\s*(.+?)(?:\n|$)", result)
    if m: info["financing"] = m.group(1).strip()
    # 公司类型
    m = re.search(r"(?:公司类型|企业类型)[：:]\s*(.+?)(?:\n|$)", result)
    if m: info["company_type"] = m.group(1).strip()

    return info


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


def fetch_work_address(page):
    """从详情页提取具体工作地址。"""
    result = page.run_js('''
return (function() {
    // 尝试多种方式找地址
    var loc = document.querySelector(\".location-address\");
    if (loc) return loc.textContent.trim();
    loc = document.querySelector(\"[class*=address]\");
    if (loc) return loc.textContent.trim();
    // 从公司信息区找
    var all = document.querySelectorAll(\"*\");
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        if (!el.offsetParent || el.children.length > 0) continue;
        var t = (el.textContent || \"\").trim();
        if (t.indexOf(\"地址\") >= 0 && t.length < 100) return t;
        if (t.indexOf(\"上海市\") === 0 && t.length < 100) return t;
    }
    return \"\";
})();
''')
    return result.strip() if result else ""


def check_english_requirement(jd_text, config=None):
    """检查JD中是否有硬性英语要求。返回命中的关键词列表。"""
    if config is None:
        config = {}
    hard_kws = config.get("english_hard_keywords", [])
    ok_kws = config.get("english_ok_keywords", [])
    hits = []
    if jd_text:
        for kw in hard_kws:
            if kw.lower() in jd_text.lower():
                hits.append(("hard", kw))
        for kw in ok_kws:
            if kw.lower() in jd_text.lower():
                hits.append(("ok", kw))
    return hits


def fetch_recruiter_name(page):
    """从BOSS详情页提取招聘者姓名。BOSS页面在 [class*=boss-info] 区域展示：
    第一行: 叶女士/施先生（姓名+性别）
    第二行: 刚刚活跃/当前在线
    第三行: 公司名·招聘者/HR经理（公司+职位）
    返回 {'surname': '叶', 'full': '叶女士', 'gender': 'female', 'role': 'HR经理'} 或 {}。"""
    result = page.run_js('''
return (function() {
    var sections = document.querySelectorAll("[class*=boss-info]");
    for (var i = 0; i < sections.length; i++) {
        var text = sections[i].textContent.trim();
        var lines = text.split(String.fromCharCode(10)).map(function(l) { return l.trim(); }).filter(function(l) { return l; });
        if (lines.length >= 1) {
            // Return first 3 lines: [name, status, company·role]
            return JSON.stringify(lines.slice(0, 3));
        }
    }
    return "";
})();
''')
    result = (result or "").strip()
    if not result:
        return {}

    try:
        lines = json.loads(result)
    except json.JSONDecodeError:
        return {}

    if not lines or len(lines) < 1:
        return {}

    info = {}
    name_line = lines[0]  # "叶女士" or "施先生"

    # 解析姓名和性别
    m = re.match(r'^([一-龥]{1,2})(女士|先生)', name_line)
    if m:
        info['surname'] = m.group(1)
        info['gender'] = 'female' if '女士' in m.group(2) else 'male'
        info['full'] = name_line
    else:
        # 降级：没有女士/先生后缀，可能是全名展示（如"张芳云"）
        # 中文姓氏99%是单字（复姓如欧阳/司马为双字），优先取首字
        surname_m = re.match(r'^([一-龥])', name_line)
        if surname_m:
            info['surname'] = surname_m.group(1)
            info['full'] = name_line
            # 尝试从2-3字的全名判断性别（不精确，标记为未知）

    # 解析职位（第三行: "公司名·HR经理"）
    if len(lines) >= 3:
        role_line = lines[2]
        role_m = re.search(r'[··](.+)$', role_line)
        if role_m:
            info['role'] = role_m.group(1).strip()

    return info


def fetch_jds_for(page, cards, count, config=None):
    """逐个打开详情页读取JD + 提取明文薪资 + 提取通勤信息 + 招聘者姓名。"""
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

            # 提取招聘者姓名
            recruiter = fetch_recruiter_name(page)
            if recruiter:
                card["recruiter_name"] = recruiter
                print(f" | HR:{recruiter.get('full','?')}", end="")

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
            # 公司信息抓取
            comp = fetch_company_info(page)
            if comp:
                card["company_info"] = comp
                if comp.get("registered_capital_wan", 999) < 50:
                    print(f" | ⚠️小公司({comp.get('registered_capital','?')})", end="")

            # 工作地址提取 + 通勤计算
            addr = fetch_work_address(page)
            if addr:
                card["work_address"] = addr
                home = (config or {}).get("home", {}).get("address", "")
                gaode_key = (config or {}).get("gaode_api_key", "")
                if home and gaode_key:
                    commute = calculate_commute(home, addr, gaode_key)
                    if commute:
                        card["commute_info"] = commute
                        parts = []
                        if commute.get('bike_min') and commute['bike_min'] <= 30:
                            parts.append(f"骑行{commute['bike_min']}分钟")
                        if commute.get('transit_min'):
                            parts.append(f"公交{commute['transit_min']}分钟")
                        if commute.get('drive_min') and commute.get('distance_km', 0) and commute['distance_km'] > 10:
                            parts.append(f"驾车{commute['drive_min']}分钟")
                        print(f" | 通勤: {' | '.join(parts)}", end="")

            # 英语要求检测
            eng_hits = check_english_requirement(card.get("jd_text", ""), config)
            if eng_hits:
                card["english_required"] = [kw for t, kw in eng_hits]
                print(f" | ⚠️ENG:{','.join(card['english_required'][:2])}", end="")
            print()
        except Exception as e:
            if not card.get("jd_text") or card["jd_text"].startswith("["):
                card["jd_text"] = f"[读取失败: {e}]"
            print(f"WARN: {e}")
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
    config = load_config(SKILL_DIR)
    cards = fetch_jds_for(page, cards, top_n, config)

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
