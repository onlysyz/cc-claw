"""CC-Claw Hook Config - Manages Claude Code settings.json hook injection"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
BACKUP_SUFFIX = ".bak"


def _load_settings() -> dict:
    """Load settings.json, return empty dict if missing or invalid."""
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not read {SETTINGS_PATH}: {e}, starting fresh")
        return {}


def _save_settings(data: dict):
    """Save settings.json atomically."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.rename(SETTINGS_PATH)


def _backup_settings():
    """Create a backup of settings.json before modifying."""
    if SETTINGS_PATH.exists():
        shutil.copy2(SETTINGS_PATH, str(SETTINGS_PATH) + BACKUP_SUFFIX)
        logger.info(f"Backed up settings.json → {SETTINGS_PATH.name}{BACKUP_SUFFIX}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_hook_port() -> int:
    """Return the port the hook server runs on."""
    config_dir = Path.home() / ".config" / "cc-claw"
    port_file = config_dir / "hook_port.txt"
    if port_file.exists():
        try:
            return int(port_file.read_text().strip())
        except ValueError:
            pass
    return 3456


def inject_hooks(hook_port: Optional[int] = None) -> bool:
    """Inject cc-claw hooks into ~/.claude/settings.json.

    Merges hook entries without disturbing existing permissions/env/config.
    Creates a backup first.

    Returns True if injection succeeded.
    """
    if hook_port is None:
        hook_port = get_hook_port()

    base_url = f"http://127.0.0.1:{hook_port}"

    cc_claw_hooks = {
        "Stop": [
            {
                "type": "http",
                "url": f"{base_url}/hooks/stop?task_id=$CC_CLAW_TASK_ID",
                "timeout": 30,
                "allowedEnvVars": ["CC_CLAW_TASK_ID"],
            }
        ],
        "PostToolUse": [
            {
                "type": "http",
                "url": f"{base_url}/hooks/post-tool-use?task_id=$CC_CLAW_TASK_ID",
                "timeout": 10,
                "allowedEnvVars": ["CC_CLAW_TASK_ID"],
            }
        ],
        "PreToolUse": [
            {
                "type": "http",
                "url": f"{base_url}/hooks/pre-tool-use?task_id=$CC_CLAW_TASK_ID",
                "timeout": 10,
                "allowedEnvVars": ["CC_CLAW_TASK_ID"],
            }
        ],
        "Notification": [
            {
                "type": "http",
                "url": f"{base_url}/hooks/notification?task_id=$CC_CLAW_TASK_ID",
                "timeout": 10,
                "allowedEnvVars": ["CC_CLAW_TASK_ID"],
            }
        ],
    }

    _backup_settings()
    settings = _load_settings()

    # Merge hooks (don't overwrite existing hooks, just append cc-claw's)
    existing_hooks = settings.get("hooks", {})
    if "hooks" not in settings:
        settings["hooks"] = {}

    for event_name, hooks in cc_claw_hooks.items():
        if event_name not in settings["hooks"]:
            settings["hooks"][event_name] = []
        # Append cc-claw hooks that aren't already registered
        existing_urls = {h.get("url", "") for h in settings["hooks"][event_name]}
        for hook in hooks:
            if hook["url"] not in existing_urls:
                settings["hooks"][event_name].append(hook)

    _save_settings(settings)
    logger.info(f"Injected cc-claw hooks into {SETTINGS_PATH} (port={hook_port})")
    return True


def remove_hooks() -> bool:
    """Remove cc-claw hooks from settings.json, restoring original.

    Returns True if removal succeeded (or nothing to remove).
    """
    if not SETTINGS_PATH.exists():
        return True

    settings = _load_settings()
    hooks = settings.get("hooks", {})

    cc_claw_markers = [
        "/hooks/stop", "/hooks/post-tool-use",
        "/hooks/pre-tool-use", "/hooks/notification",
    ]
    changed = False

    for event_name in list(hooks.keys()):
        original_len = len(hooks[event_name])
        hooks[event_name] = [
            h for h in hooks[event_name]
            if not any(marker in h.get("url", "") for marker in cc_claw_markers)
        ]
        if len(hooks[event_name]) != original_len:
            changed = True
        # Remove empty event arrays
        if not hooks[event_name]:
            del hooks[event_name]

    if changed:
        if hooks:
            settings["hooks"] = hooks
        else:
            settings.pop("hooks", None)
        _save_settings(settings)
        logger.info(f"Removed cc-claw hooks from {SETTINGS_PATH}")
    else:
        logger.info("No cc-claw hooks found to remove")

    return True


def is_hooks_injected() -> bool:
    """Check whether cc-claw hooks are currently registered."""
    settings = _load_settings()
    hooks = settings.get("hooks", {})
    cc_claw_markers = [
        "/hooks/stop", "/hooks/post-tool-use",
        "/hooks/pre-tool-use", "/hooks/notification",
    ]
    for event_hooks in hooks.values():
        for h in event_hooks:
            if any(marker in h.get("url", "") for marker in cc_claw_markers):
                return True
    return False
