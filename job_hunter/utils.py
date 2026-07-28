"""工具函数：文本清洗、薪资解析、日志读写、命令行参数。"""

import argparse
import json
import re
from pathlib import Path


def clean_text(text):
    """清理CSS残留和特殊字符。"""
    text = re.sub(r"\.[a-zA-Z]+\{.*?\}", "", text)
    text = re.sub(r"[-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_salary_min(salary_str):
    """从薪资字符串提取最低月薪（K为单位）。

    '8-12K' → 8, '20-25K·13薪' → 20, None → None
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
