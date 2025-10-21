#!/usr/bin/env bash
# POE-20251021-0001: Signature correctness & atomic commit
# Evidence tier: SPEC (exec-ready when testbed available)
# Exit codes: 0=mitigated, 50=inconclusive, 100=vulnerable

set -euo pipefail

TARGET_SCRIPT="${TARGET_SCRIPT:-./nyx-targets/audit_triad.py}"
LEDGER_PATH="${LEDGER_PATH:-/tmp/nyx-ledger.json}"

if ! command -v gpg >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  echo "INCONCLUSIVE: missing gpg or python3"
  exit 50
fi

# Fresh workspace
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
export GNUPGHOME="$WORKDIR/gnupg"
mkdir -p "$GNUPGHOME"; chmod 700 "$GNUPGHOME"

# Ephemeral key
cat >"$WORKDIR/keygen.txt" <<'EOF'
%no-protection
Key-Type: RSA
Key-Length: 2048
Name-Real: NYX Test Key
Name-Email: nyx-test@local
Expire-Date: 0
EOF
gpg --batch --gen-key "$WORKDIR/keygen.txt" >/dev/null 2>&1 || { echo "INCONCLUSIVE: keygen failed"; exit 50; }
KEY_ID="$(gpg --list-keys --with-colons | awk -F: '/^pub/ {print $5; exit}')"
[[ -n "$KEY_ID" ]] || { echo "INCONCLUSIVE: no key id"; exit 50; }

# 1) Run the target to produce ledger + detached signature
python3 "$TARGET_SCRIPT" --ledger "$LEDGER_PATH" --gpg-key "$KEY_ID" >/dev/null 2>&1 || true

# 2) Verify signature against current bytes
if ! gpg --verify "${LEDGER_PATH}.asc" "$LEDGER_PATH" >/dev/null 2>&1; then
  echo "VULNERABLE: signature does not validate final on-disk bytes (sign-then-mutate / non-atomic write suspected)"
  exit 100
fi

# 3) Compute pre/post hashes to confirm immutability around verify
HASH_BEFORE="$(sha256sum "$LEDGER_PATH" | awk '{print $1}')"
gpg --verify "${LEDGER_PATH}.asc" "$LEDGER_PATH" >/dev/null 2>&1 || { echo "INCONCLUSIVE: intermittent verify failure"; exit 50; }
HASH_AFTER="$(sha256sum "$LEDGER_PATH" | awk '{print $1}')"

if [[ "$HASH_BEFORE" != "$HASH_AFTER" ]]; then
  echo "VULNERABLE: ledger bytes changed between checks; commit is not stable/atomic"
  exit 100
fi

# Optional TOCTOU probe (operator can toggle): mutate during verify window to see if signer is racing
# echo "tamper" >> "$LEDGER_PATH" && gpg --verify "${LEDGER_PATH}.asc" "$LEDGER_PATH" >/dev/null 2>&1 && { echo "VULNERABLE: verify passed after mutation"; exit 100; }

echo "MITIGATED: signature verifies and bytes are stable (no evidence of sign-then-mutate or non-atomic commit)"
exit 0
