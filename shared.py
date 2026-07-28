"""公共模块 — 向后兼容的 re-export 层。

实现已迁移至 job_hunter/ 包内各模块。此文件保留以确保
现有适配器脚本 ``from shared import ...`` 仍可正常工作。
"""

from job_hunter.browser import connect_chrome
from job_hunter.config import DEFAULT_CONFIG, load_config
from job_hunter.scorer import dedup_key, is_blacklisted, score_jd
from job_hunter.utils import (
    load_applied_index,
    load_log,
    parse_common_args,
    print_summary,
    record,
    save_log,
)

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
