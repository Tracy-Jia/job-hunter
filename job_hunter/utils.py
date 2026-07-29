"""工具函数：文本清洗、薪资解析、日志读写、命令行参数。"""

import argparse
import json
import re
import ssl
import urllib.request
import urllib.parse
from pathlib import Path


def clean_text(text):
    """清理CSS残留和特殊字符。"""
    text = re.sub(r"\.[a-zA-Z]+\{.*?\}", "", text)
    text = re.sub(r"[-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def decode_boss_salary(raw):
    """解码BOSS直聘自定义字体加密的薪资。
    PUA字符 U+E031-U+E03A 映射数字 0-9.
    """
    if not raw:
        return raw
    result = []
    for ch in raw:
        code = ord(ch)
        if 0xE031 <= code <= 0xE03A:
            result.append(str(code - 0xE031))
        else:
            result.append(ch)
    return ''.join(result)


def parse_salary_min(salary_str):
    """从薪资字符串提取最低月薪（K为单位）。
    '8-12K' -> 8, '20-25K·13薪' -> 20, None -> None
    """
    if not salary_str:
        return None
    m = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*[Kk]", salary_str)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*[Kk]", salary_str)
    if m:
        return int(m.group(1))
    return None


def calculate_commute(origin, destination, api_key=None):
    """用高德地图API计算公交/驾车通勤时间。
    返回: {'transit_min': 45, 'drive_min': 25, 'distance_km': 12.3} 或 None
    """
    if not api_key:
        return None
    ctx = ssl.create_default_context()

    def _get(url):
        req = urllib.request.Request(url)
        return json.loads(urllib.request.urlopen(req, timeout=10, context=ctx).read().decode('utf-8'))

    try:
        city_q = urllib.parse.quote('上海')
        orig_url = 'https://restapi.amap.com/v3/geocode/geo?key=' + api_key + '&address=' + urllib.parse.quote(origin) + '&city=' + city_q
        oresp = _get(orig_url)
        orig_loc = oresp['geocodes'][0]['location'] if oresp.get('geocodes') else None

        dest_url = 'https://restapi.amap.com/v3/geocode/geo?key=' + api_key + '&address=' + urllib.parse.quote(destination) + '&city=' + city_q
        dresp = _get(dest_url)
        dest_loc = dresp['geocodes'][0]['location'] if dresp.get('geocodes') else None

        if not orig_loc or not dest_loc:
            return None

        transit_min = None
        t_url = 'https://restapi.amap.com/v3/direction/transit/integrated?key=' + api_key + '&origin=' + orig_loc + '&destination=' + dest_loc + '&city=' + city_q
        tresp = _get(t_url)
        if tresp.get('route', {}).get('transits'):
            transit_min = round(int(tresp['route']['transits'][0]['duration']) / 60)

        drive_min = None
        dist_km = None
        d_url = 'https://restapi.amap.com/v3/direction/driving?key=' + api_key + '&origin=' + orig_loc + '&destination=' + dest_loc
        dresp = _get(d_url)
        if dresp.get('route', {}).get('paths'):
            p = dresp['route']['paths'][0]
            drive_min = round(int(p.get('duration', 0)) / 60)
            dist_km = round(int(p.get('distance', 0)) / 1000, 1)

        # 骑行（用于判断电瓶车通勤可行性）
        bike_min = None
        b_url = 'https://restapi.amap.com/v4/direction/bicycling?key=' + api_key + '&origin=' + orig_loc + '&destination=' + dest_loc
        try:
            bresp = _get(b_url)
            if bresp.get('data', {}).get('paths'):
                bike_min = round(int(bresp['data']['paths'][0].get('duration', 0)) / 60)
        except Exception:
            pass

        return {
            'transit_min': transit_min,
            'drive_min': drive_min,
            'bike_min': bike_min,
            'distance_km': dist_km,
        }
    except Exception:
        return None


def _norm(text) -> str:
    """归一化：去首尾/合并内部空白 + 转小写。"""
    return " ".join(str(text or "").split()).lower()


def dedup_key(company, title) -> str:
    """去重键 = 归一化(公司)||归一化(标题)。"""
    c = _norm(company)
    t = _norm(title)
    if not c and not t:
        return ""
    return f"{c}||{t}"


def load_applied_index(skill_dir: Path | None = None) -> set[str]:
    """扫描目录下所有 *-log.json 的 applied[]，聚合成已投索引。"""
    skill_dir = skill_dir or Path(".")
    index: set[str] = set()
    for log_file in skill_dir.glob("*-log.json"):
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for entry in data.get("applied", []):
            key = dedup_key(entry.get("company", ""), entry.get("job", ""))
            if key:
                index.add(key)
    return index


# ---------- 日志 ----------


def load_log(log_file: Path) -> dict:
    if log_file.exists():
        return json.loads(log_file.read_text(encoding="utf-8"))
    return {"applied": [], "skipped": [], "failed": []}


def save_log(log: dict, log_file: Path):
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def record(log: dict, log_file: Path, bucket: str, entry: dict) -> dict:
    """把一条记录追加到 log[bucket]（applied/skipped/failed）并落盘。"""
    log[bucket].append(entry)
    save_log(log, log_file)
    return log


def print_summary(platform: str, applied: int, skipped: int, log_file: Path):
    """统一的结尾汇总框。"""
    print(
        f"""
╔══════════════════════════════════╗
  {platform} 投递完成
  成功: {applied} 份  跳过: {skipped} 份
  日志: {log_file}
╚══════════════════════════════════╝
"""
    )


# ---------- 命令行参数 ----------


def parse_common_args(
    city_codes: dict,
    *,
    default_city: str = "全国",
    default_count: int = 20,
    default_min_score: int = 60,
    count_help: str = "投递数量",
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """各平台通用的命令行参数：--job / --city / --count / --min-score。"""
    p = argparse.ArgumentParser()
    p.add_argument("--job", required=True, help="搜索岗位名")
    p.add_argument("--city", default=default_city, help=f"城市，可选: {list(city_codes)}")
    p.add_argument("--count", type=int, default=default_count, help=count_help)
    p.add_argument("--min-score", type=int, default=default_min_score, help="最低评分（0=不过滤）")
    return p.parse_args(argv)
