"""Fail-closed verification for PROTECTED-LINE-GUARD."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "PROTECTED-LINE-GUARD"


def parse_guard(text: str):
    allowed, forbidden, operations = [], [], []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("FILE: "):
            path = line[len("FILE: "):].rstrip("\r\n")
            i += 1
            if i >= len(lines):
                raise ValueError(f"missing block marker for {path}")
            marker = lines[i].rstrip("\r\n")
            if marker not in {"--- BEGIN ALLOWED ---", "--- BEGIN FORBIDDEN ---"}:
                raise ValueError(f"FILE {path} has invalid block marker")
            kind = "allowed" if "ALLOWED" in marker else "forbidden"
            end = "--- END ALLOWED ---" if kind == "allowed" else "--- END FORBIDDEN ---"
            i += 1
            start = i
            while i < len(lines) and lines[i].rstrip("\r\n") != end:
                i += 1
            if i >= len(lines):
                raise ValueError(f"unterminated {kind} block for {path}")
            (allowed if kind == "allowed" else forbidden).append((path, "".join(lines[start:i])))
        elif line.rstrip("\r\n") == "--- BEGIN OPERATION ---":
            i += 1
            if i >= len(lines) or not lines[i].startswith("FILE: "):
                raise ValueError("operation has no FILE line")
            path = lines[i][len("FILE: "):].rstrip("\r\n")
            i += 1
            if i >= len(lines) or lines[i].rstrip("\r\n") != "--- BEGIN PROPOSED CONTENT ---":
                raise ValueError(f"operation for {path} has no proposed-content marker")
            i += 1
            start = i
            while i < len(lines) and lines[i].rstrip("\r\n") != "--- END PROPOSED CONTENT ---":
                i += 1
            if i >= len(lines):
                raise ValueError(f"unterminated proposed content for {path}")
            operations.append((path, "".join(lines[start:i])))
        i += 1
    return allowed, forbidden, operations


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "git command failed")
    return p.stdout


def trusted_base() -> str | None:
    return os.environ.get("GUARD_BASE_REF") or os.environ.get("GITHUB_EVENT_BEFORE") or None


def main() -> int:
    if not GUARD.is_file():
        print("GUARD CHECK FAILED: Guard is missing")
        return 1
    try:
        current = GUARD.read_text(encoding="utf-8")
        allowed, forbidden, current_ops = parse_guard(current)
    except (OSError, ValueError) as exc:
        print(f"GUARD CHECK FAILED: cannot parse current Guard: {exc}")
        return 1

    failures = []
    for path, fragment in allowed:
        target = ROOT / path
        if not target.is_file():
            failures.append(f"{path}: protected file is missing")
        else:
            actual = target.read_text(encoding="utf-8")
            normalized_fragment = fragment.rstrip("\r\n")
            normalized_actual = actual.rstrip("\r\n")
            count = normalized_actual.count(normalized_fragment)
            if count != 1:
                failures.append(f"{path}: ALLOWED occurrence count={count}, expected 1")

    for path, fragment in forbidden:
        target = ROOT / path
        if not target.is_file():
            failures.append(f"{path}: FORBIDDEN target is missing")
        elif target.read_text(encoding="utf-8").rstrip("\r\n").count(fragment.rstrip("\r\n")):
            failures.append(f"{path}: FORBIDDEN fragment is present")

    base = trusted_base()
    if base:
        try:
            base_allowed, _, base_ops = parse_guard(git("show", f"{base}:PROTECTED-LINE-GUARD"))
        except (RuntimeError, ValueError) as exc:
            print(f"GUARD CHECK FAILED: cannot load trusted base Guard: {exc}")
            return 1
        protected_paths = sorted(
            {path for path, _ in base_allowed} | {path for path, _ in allowed}
        )
        for path in protected_paths:
            target = ROOT / path
            if not target.is_file():
                continue
            try:
                old = git("show", f"{base}:{path}")
            except RuntimeError as exc:
                failures.append(f"{path}: cannot read trusted base file: {exc}")
                continue
            actual = target.read_text(encoding="utf-8")
            if actual.rstrip("\r\n") != old.rstrip("\r\n"):
                if not any(
                    op_path == path
                    and proposed.rstrip("\r\n") == actual.rstrip("\r\n")
                    for op_path, proposed in base_ops
                ):
                    failures.append(
                        f"{path}: changed without an OPERATION that existed in the trusted base Guard"
                    )
    else:
        print("GUARD CHECK FAILED: trusted base revision is unavailable")
        return 1

    if current_ops:
        print(f"GUARD INFO: {len(current_ops)} pending operation proposal(s); "
              "they cannot authorize a protected change in this same commit.")

    if failures:
        print("GUARD CHECK FAILED: protected-state invariant violated")
        for item in failures:
            print(f" - {item}")
        return 1

    print(f"GUARD CHECK PASSED: {len(allowed)} ALLOWED, {len(forbidden)} FORBIDDEN, "
          f"{len(current_ops)} pending operations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
