from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OPERATIONS_FILE = DATA_DIR / "operations.json"
DATA_LOCK = Lock()


app = Flask(__name__)


SEED_OPERATIONS = [
    {
        "id": "op-system-c",
        "title": "System Drive C:\\ - Military Grade Wipe",
        "targetPath": "C:\\",
        "sizeLabel": "500 GB",
        "wipeType": "military",
        "includeSubfolders": "yes",
        "verifyWipe": "yes",
        "customPasses": 7,
        "status": "completed",
        "progress": 100,
        "durationMinutes": 240,
        "startedAt": "2026-04-28T08:00:00Z",
        "completedAt": "2026-04-28T12:00:00Z",
    },
    {
        "id": "op-usb-drive",
        "title": "External USB Drive - Secure Wipe",
        "targetPath": "E:\\USB_DRIVE",
        "sizeLabel": "64 GB",
        "wipeType": "secure",
        "includeSubfolders": "yes",
        "verifyWipe": "yes",
        "customPasses": 3,
        "status": "running",
        "progress": 75,
        "durationMinutes": 45,
        "startedAt": "2026-04-29T07:57:00Z",
        "completedAt": None,
    },
    {
        "id": "op-browser-cache",
        "title": "Browser Cache & Temp Files - Quick Wipe",
        "targetPath": "%TEMP%; %APPDATA%\\Local\\Temp",
        "sizeLabel": "1.2 GB",
        "wipeType": "quick",
        "includeSubfolders": "yes",
        "verifyWipe": "no",
        "customPasses": 1,
        "status": "pending",
        "progress": 55,
        "durationMinutes": 10,
        "startedAt": "2026-04-29T08:26:00Z",
        "completedAt": None,
    },
    {
        "id": "op-temp-secure",
        "title": "Data Wipe: C:\\temp (secure)",
        "targetPath": "C:\\temp",
        "sizeLabel": "8 GB",
        "wipeType": "secure",
        "includeSubfolders": "yes",
        "verifyWipe": "yes",
        "customPasses": 3,
        "status": "pending",
        "progress": 10,
        "durationMinutes": 45,
        "startedAt": "2026-04-29T08:31:00Z",
        "completedAt": None,
    },
    {
        "id": "op-downloads",
        "title": "Downloads Folder Cleanup - Quick Wipe",
        "targetPath": "C:\\Users\\%USERNAME%\\Downloads",
        "sizeLabel": "14 GB",
        "wipeType": "quick",
        "includeSubfolders": "no",
        "verifyWipe": "yes",
        "customPasses": 1,
        "status": "completed",
        "progress": 100,
        "durationMinutes": 10,
        "startedAt": "2026-04-27T09:00:00Z",
        "completedAt": "2026-04-27T09:12:00Z",
    },
    {
        "id": "op-client-archive",
        "title": "Client Archive Overwrite - Custom Pattern",
        "targetPath": "D:\\ClientArchive",
        "sizeLabel": "220 GB",
        "wipeType": "custom",
        "includeSubfolders": "yes",
        "verifyWipe": "yes",
        "customPasses": 12,
        "status": "failed",
        "progress": 63,
        "durationMinutes": 120,
        "startedAt": "2026-04-26T05:30:00Z",
        "completedAt": "2026-04-26T06:41:00Z",
    },
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_data_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not OPERATIONS_FILE.exists():
        OPERATIONS_FILE.write_text(json.dumps(SEED_OPERATIONS, indent=2), encoding="utf-8")


def load_operations() -> list[dict]:
    ensure_data_file()
    with DATA_LOCK:
        return json.loads(OPERATIONS_FILE.read_text(encoding="utf-8"))


def save_operations(operations: list[dict]) -> None:
    ensure_data_file()
    with DATA_LOCK:
        OPERATIONS_FILE.write_text(json.dumps(operations, indent=2), encoding="utf-8")


def estimate_duration_minutes(wipe_type: str, custom_passes: int) -> int:
    defaults = {
        "quick": 10,
        "secure": 45,
        "military": 240,
        "custom": max(20, custom_passes * 8),
    }
    return defaults.get(wipe_type, 60)


def estimate_size_label(target_path: str) -> str:
    quick_map = {
        "C:\\temp": "8 GB",
        "C:\\Users\\%USERNAME%\\Downloads": "14 GB",
        "%APPDATA%\\Local\\Temp": "1.2 GB",
        "C:\\Windows\\Temp": "500 MB",
        "D:\\": "100 GB",
        "/tmp": "1 GB",
        "C:\\": "500 GB",
        "E:\\USB_DRIVE": "64 GB",
    }
    if target_path in quick_map:
        return quick_map[target_path]
    if re.fullmatch(r"[A-Za-z]:\\", target_path):
        return "250 GB"
    if "temp" in target_path.lower():
        return "2 GB"
    if "download" in target_path.lower():
        return "12 GB"
    return "4 GB"


def pretty_target_name(target_path: str) -> str:
    quick_labels = {
        "C:\\temp": "Temporary Files",
        "C:\\Users\\%USERNAME%\\Downloads": "Downloads Folder",
        "%APPDATA%\\Local\\Temp": "Browser Cache & Temp Files",
        "C:\\Windows\\Temp": "System Temp Files",
        "D:\\": "Entire D: Drive",
        "/tmp": "Unix Temp Directory",
        "C:\\": "System Drive C:\\",
        "E:\\USB_DRIVE": "External USB Drive",
    }
    if target_path in quick_labels:
        return quick_labels[target_path]
    cleaned = target_path.rstrip("\\/")
    parts = re.split(r"[\\/]", cleaned)
    name = parts[-1] if parts and parts[-1] else cleaned
    name = name.replace("_", " ").replace("%USERNAME%", "User")
    return name if len(name) > 2 else cleaned


def create_operation_title(payload: dict) -> str:
    wipe_type = payload["wipeType"]
    target_path = payload["targetPath"]
    wipe_names = {
        "quick": "Quick Wipe",
        "secure": "Secure Wipe",
        "military": "Military Grade Wipe",
        "custom": "Custom Pattern Wipe",
    }
    target_name = pretty_target_name(target_path)
    if target_path == "C:\\" and wipe_type == "military":
        return "System Drive C:\\ - Military Grade Wipe"
    if target_path == "E:\\USB_DRIVE":
        return f"{target_name} - {wipe_names.get(wipe_type, 'Wipe')}"
    if target_path in {"%APPDATA%\\Local\\Temp", "C:\\Windows\\Temp", "/tmp"}:
        return f"{target_name} - {wipe_names.get(wipe_type, 'Wipe')}"
    return f"Data Wipe: {target_path} ({wipe_type})"


def normalize_payload(payload: dict) -> dict:
    wipe_type = payload.get("wipeType", "secure")
    target_path = str(payload.get("targetPath", "")).strip()
    custom_passes = payload.get("customPasses", 7)
    try:
        custom_passes = int(custom_passes)
    except (TypeError, ValueError):
        custom_passes = 7
    custom_passes = max(1, min(custom_passes, 35))
    return {
        "wipeType": wipe_type,
        "targetPath": target_path,
        "customPasses": custom_passes,
        "includeSubfolders": payload.get("includeSubfolders", "yes"),
        "verifyWipe": payload.get("verifyWipe", "yes"),
    }


def create_operation(payload: dict) -> dict:
    normalized = normalize_payload(payload)
    now = utc_now()
    return {
        "id": f"op-{uuid.uuid4().hex[:10]}",
        "title": create_operation_title(normalized),
        "targetPath": normalized["targetPath"],
        "sizeLabel": estimate_size_label(normalized["targetPath"]),
        "wipeType": normalized["wipeType"],
        "includeSubfolders": normalized["includeSubfolders"],
        "verifyWipe": normalized["verifyWipe"],
        "customPasses": normalized["customPasses"],
        "status": "pending",
        "progress": 0,
        "durationMinutes": estimate_duration_minutes(
            normalized["wipeType"], normalized["customPasses"]
        ),
        "startedAt": to_iso(now),
        "completedAt": None,
    }


def simulate_operations(operations: list[dict]) -> list[dict]:
    now = utc_now()
    changed = False

    for operation in operations:
        if operation["status"] in {"completed", "failed"}:
            continue

        started_at = parse_iso(operation.get("startedAt"))
        if started_at is None:
            started_at = now
            operation["startedAt"] = to_iso(started_at)
            changed = True

        total_seconds = max(60, int(operation.get("durationMinutes", 1) * 60))
        elapsed_seconds = max(0, int((now - started_at).total_seconds()))
        progress_ratio = min(1.0, elapsed_seconds / total_seconds)
        progress = min(100, max(0, int(round(progress_ratio * 100))))

        if progress >= 100:
            if operation["status"] != "completed":
                operation["status"] = "completed"
                operation["progress"] = 100
                operation["completedAt"] = to_iso(started_at + timedelta(seconds=total_seconds))
                changed = True
            continue

        pending_threshold = 0.18
        new_status = "pending" if progress_ratio < pending_threshold else "running"

        if new_status == "pending":
            progress = max(progress, 3)
            progress = min(progress, 24)
        else:
            progress = max(progress, 25)
            progress = min(progress, 99)

        if operation["status"] != new_status or operation["progress"] != progress:
            operation["status"] = new_status
            operation["progress"] = progress
            changed = True

    if changed:
        save_operations(operations)
    return operations


def to_taskade_node(operation: dict) -> dict:
    return {
        "id": operation["id"],
        "fieldValues": {
            "/text": operation["title"],
            "/attributes/@wipe1": operation["wipeType"],
            "/attributes/@targ1": operation["targetPath"],
            "/attributes/@size1": operation["sizeLabel"],
            "/attributes/@stat1": operation["status"],
            "/attributes/@prog1": operation["progress"],
            "/attributes/@time1": operation["startedAt"],
            "/attributes/@comp1": operation["completedAt"],
        },
    }


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/health")
def health() -> tuple[dict, int]:
    return {"ok": True, "service": "SecureWipe Pro"}, 200


@app.get("/api/taskade/projects/vvVAsZdSCLoXYt1p/nodes")
def get_nodes():
    operations = simulate_operations(load_operations())
    return jsonify(
        {
            "ok": True,
            "payload": {
                "nodes": [to_taskade_node(operation) for operation in operations],
            },
        }
    )


@app.post("/api/taskade/forms/01K4R1ZMD1B07FFN5NAFM35BCN/run")
def run_wipe():
    payload = request.get_json(silent=True) or {}
    normalized = normalize_payload(payload)
    if not normalized["targetPath"]:
        return jsonify({"ok": False, "error": "Target path is required."}), 400

    operations = load_operations()
    operation = create_operation(normalized)
    operations.append(operation)
    save_operations(operations)

    return (
        jsonify(
            {
                "ok": True,
                "payload": {
                    "node": to_taskade_node(operation),
                },
            }
        ),
        201,
    )


if __name__ == "__main__":
    ensure_data_file()
    app.run(debug=True, host="0.0.0.0", port=5000)
