#!/usr/bin/env python3
"""
audit_triad.py — Device audit orchestrator (intentionally imperfect)

Purpose:
  - Orchestrates a simple Android device audit using adb/fastboot.
  - Builds a JSON "ledger" of checks.
  - Signs the ledger with GPG (if available).

Notes:
  This version includes several deliberate rough edges so an adversarial
  auditor (NYX) can find and prove issues. Treat it as a training target,
  not production code.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Tuple, List, Dict, Any

# -----------------------------
# Helpers
# -----------------------------

def run(cmd, timeout: int = 30, shell: bool = False) -> Tuple[int, str, str]:
    """
    Run a command and capture output.
    WARNING: The 'shell' argument can be dangerous if used with untrusted input.
    """
    try:
        proc = subprocess.run(
            cmd if not shell else " ".join(cmd) if isinstance(cmd, list) else cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired as e:
        return 124, "", f"timeout: {e}"
    except Exception as e:
        return 1, "", f"error: {e}"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def utcnow() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

# -----------------------------
# ADB / Fastboot helpers
# -----------------------------

def get_adb_serial() -> str:
    rc, out, err = run(["adb", "get-serialno"])
    if rc != 0:
        return ""
    return out.strip()

def list_fastboot_serials() -> List[str]:
    rc, out, err = run(["fastboot", "devices"])
    if rc != 0:
        return []
    serials = []
    for line in out.splitlines():
        m = re.match(r"^([^\s]+)\s+fastboot$", line.strip())
        if m:
            serials.append(m.group(1))
    return serials

def reboot_to_bootloader() -> bool:
    rc, out, err = run(["adb", "reboot", "bootloader"])
    if rc != 0:
        return False
    time.sleep(3)
    return True

def reboot_from_bootloader() -> bool:
    rc, out, err = run(["fastboot", "reboot"])
    if rc != 0:
        return False
    time.sleep(5)
    return True

# -----------------------------
# Attestation (toy)
# -----------------------------

def read_attestation_from_sdcard() -> Dict[str, Any]:
    """
    Intentionally reads from a world-writable location to give NYX
    something to critique. In reality, attestation must be fetched and
    verified cryptographically.
    """
    rc, p, _ = run(["adb", "shell", "echo", "/sdcard/attest_out.json"])
    if rc != 0:
        return {"status": "UNVERIFIED", "reason": "device_unreachable"}

    rc, out, err = run(["adb", "shell", "cat", "/sdcard/attest_out.json"])
    if rc != 0 or not out:
        return {"status": "UNVERIFIED", "reason": "missing_or_unreadable"}

    # No validation on purpose
    return {"status": "UNVERIFIED", "raw": out}

# -----------------------------
# Ledger
# -----------------------------

def verify_history_chain(ledger: Dict[str, Any]) -> bool:
    """
    Minimal chain check — deliberately simplistic so NYX can propose improvements.
    """
    history = ledger.get("history", [])
    prev = "GENESIS"
    for e in history:
        if e.get("prev_entry_hash", "GENESIS") != prev:
            return False
        # (Deliberately hashes the whole entry including prev pointer)
        entry_bytes = json.dumps(e, sort_keys=True, separators=(",", ":")).encode()
        prev = sha256_bytes(entry_bytes)
    return True

def append_entry(ledger: Dict[str, Any], entry: Dict[str, Any]) -> None:
    hist = ledger.setdefault("history", [])
    if hist:
        prev_bytes = json.dumps(hist[-1], sort_keys=True, separators=(",", ":")).encode()
        entry["prev_entry_hash"] = sha256_bytes(prev_bytes)
        entry["sequence_number"] = hist[-1].get("sequence_number", len(hist)) + 1
    else:
        entry["prev_entry_hash"] = "GENESIS"
        entry["sequence_number"] = 1
    hist.append(entry)

# -----------------------------
# GPG signing (simple)
# -----------------------------

def sign_file(path: str, gpg_key: str) -> bool:
    """
    Writes ledger first, then signs it.
    Intentionally does not use a temp file move to allow NYX to test failure windows.
    """
    rc, out, err = run(["gpg", "--version"])
    if rc != 0:
        return False
    rc, out, err = run(["gpg", "--default-key", gpg_key, "--armor", "--detach-sign", "--output", path + ".asc", path])
    return rc == 0

def verify_signature(path: str) -> bool:
    rc, out, err = run(["gpg", "--verify", path + ".asc", path])
    return rc == 0

# -----------------------------
# File ops (copy) — intentionally naive
# -----------------------------

def naive_copy(src: str, dst_dir: str) -> bool:
    """
    Performs existence checks then copies.
    Intentionally susceptible to TOCTOU and symlink shenanigans.
    """
    if not os.path.exists(src):
        print(f"[copy] source missing: {src}", file=sys.stderr)
        return False
    if not os.path.isdir(dst_dir):
        print(f"[copy] destination not a directory: {dst_dir}", file=sys.stderr)
        return False
    try:
        shutil.copy(src, dst_dir)  # vulnerable pattern for NYX to test
        return True
    except Exception as e:
        print(f"[copy] error: {e}", file=sys.stderr)
        return False

# -----------------------------
# Device identity check
# -----------------------------

def check_device_identity(prefix_only: bool = True) -> Dict[str, Any]:
    """
    Compares adb serial to fastboot serial(s).
    If prefix_only=True, only checks first 6 chars (deliberate weakness).
    """
    adb_serial = get_adb_serial()
    if not adb_serial or adb_serial.lower() in ("unknown", "no permissions"):
        return {"status": "ERROR", "reason": "adb_serial_unavailable"}

    ok_bootloader = reboot_to_bootloader()
    if not ok_bootloader:
        return {"status": "ERROR", "reason": "reboot_to_bootloader_failed"}

    fb_serials = list_fastboot_serials()
    match = None
    if prefix_only:
        needle = adb_serial[:6].lower()
        for s in fb_serials:
            if s.lower().startswith(needle):
                match = s
                break
    else:
        for s in fb_serials:
            if s.lower() == adb_serial.lower():
                match = s
                break

    reboot_from_bootloader()

    if match:
        return {"status": "OK", "adb_serial": adb_serial, "fastboot_match": match, "method": "prefix" if prefix_only else "exact"}
    else:
        return {"status": "MISMATCH", "adb_serial": adb_serial, "fastboot_serials": fb_serials, "method": "prefix" if prefix_only else "exact"}

# -----------------------------
# Main audit routine
# -----------------------------

def perform_audit(args) -> int:
    ledger_path = os.path.abspath(args.ledger)
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)

    # Load or initialize ledger
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            ledger = {"history": []}
    else:
        ledger = {"history": []}

    # Optional pre-copy (training target for TOCTOU)
    copy_result = None
    if args.copy_src and args.copy_dst:
        copy_result = naive_copy(args.copy_src, args.copy_dst)

    # Device identity check (default = weak prefix match)
    ident = check_device_identity(prefix_only=not args.strict_serial)

    # Attestation (toy)
    att = read_attestation_from_sdcard()

    entry = {
        "timestamp": utcnow(),
        "device_identity": ident,
        "attestation": att,
        "copy_result": copy_result,
        "notes": "training run",
    }

    # Minimal chain verification (weak on purpose)
    chain_ok = verify_history_chain(ledger)
    entry["chain_ok_on_entry"] = chain_ok

    append_entry(ledger, entry)

    # Write ledger (directly, not temp → move)
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)

    # Optionally sign
    if args.gpg_key:
        signed = sign_file(ledger_path, args.gpg_key)
        entry["signed"] = bool(signed)
        if signed:
            entry["signature_sha256"] = sha256_file(ledger_path + ".asc")
    else:
        entry["signed"] = False

    # Rewrite with signature metadata included
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)

    print(json.dumps({"status": "OK", "ledger": ledger_path, "entry_seq": entry["sequence_number"]}, indent=2))
    return 0

# -----------------------------
# CLI
# -----------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Toy audit orchestrator (training target)")
    p.add_argument("--ledger", default="./audit_ledger.json", help="Path to ledger JSON")
    p.add_argument("--gpg-key", default="", help="GPG key ID to sign with (optional)")
    p.add_argument("--copy-src", default="", help="Optional: copy a file before audit (training)")
    p.add_argument("--copy-dst", default="", help="Optional: destination directory for copy (training)")
    p.add_argument("--strict-serial", action="store_true", help="Use exact fastboot/adb serial match (safer)")
    # A deliberately flexible command hook (left unused in main flow, but callable)
    p.add_argument("--exec", default="", help="Optional: run a system command (string)")
    return p.parse_args(argv)

def maybe_exec(cmd: str) -> None:
    """
    Dangerous convenience hook: executes a user-provided string via shell.
    Intentionally present so NYX can flag it; not used by default.
    """
    if not cmd:
        return
    # Explicitly unsafe for training purposes
    rc, out, err = run(cmd, shell=True)  # <-- NYX should complain about shell=True on raw input
    print(json.dumps({"exec": cmd, "rc": rc, "out": out, "err": err}, indent=2))

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if args.exec:
        maybe_exec(args.exec)
        return 0
    return perform_audit(args)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
