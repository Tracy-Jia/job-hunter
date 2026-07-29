"""Pipeline状态追踪，供boss.py入口显示next action提示。"""
import json
from datetime import datetime
from pathlib import Path

DEFAULT_STATE = {
    "phase": "idle",
    "last_action": None,
    "last_action_time": None,
    "next_action": "运行 boss.py scan fast 开始",
    "stats": {"fast_scanned": 0, "deep_scanned": 0, "prefiltered": 0, "sent": 0},
}

def load_state(skill_dir):
    path = skill_dir / ".pipeline-state.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_STATE)

def save_state(state, skill_dir):
    path = skill_dir / ".pipeline-state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def update_state(skill_dir, **kwargs):
    state = load_state(skill_dir)
    state["last_action_time"] = datetime.now().strftime("%m-%d %H:%M")
    if "phase" in kwargs:
        state["phase"] = kwargs.pop("phase")
    if "next_action" in kwargs:
        state["next_action"] = kwargs.pop("next_action")
    for k, v in kwargs.pop("stat_delta", {}).items():
        state["stats"][k] = state["stats"].get(k, 0) + v
    state.update(kwargs)
    save_state(state, skill_dir)

def print_state(state):
    phase = state.get("phase", "idle")
    last_time = state.get("last_action_time", "-")
    lines = [f"状态: {phase}  (上次: {last_time})"]
    if state.get("next_action"):
        lines.append(f"下一步: {state['next_action']}")
    if state.get("stats", {}).get("sent", 0):
        lines.append(f"已投递: {state['stats']['sent']} 份")
    return "\n".join(lines)
