"""job-hunter — AI辅助求职投递工具包。"""

from .browser import connect_chrome
from .config import DEFAULT_CONFIG, load_config
from .scorer import dedup_key, is_blacklisted, score_jd
from .utils import load_applied_index, load_log, parse_common_args, print_summary, record, save_log

__all__ = [
    "connect_chrome",
    "DEFAULT_CONFIG",
    "load_config",
    "dedup_key",
    "is_blacklisted",
    "score_jd",
    "load_applied_index",
    "load_log",
    "save_log",
    "record",
    "print_summary",
    "parse_common_args",
]
