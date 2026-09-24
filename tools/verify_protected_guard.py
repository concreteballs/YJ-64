"""Fail-closed verification for PROTECTED-LINE-GUARD."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "PROTECTED-LINE-GUARD"

ALLOWED_RE = re.compile(
    r"(?ms)^FILE: (.+?)\n--- BEGIN ALLOWED ---\n(.*?)\n--- END ALLOWED ---"
)
FORBIDDEN_RE = re.compile(
    r"(?ms)^FILE: (.+?)\n--- BEGIN FORBIDDEN ---\n(.*?)\n--- END FORBIDDEN ---"
)
OPERATION_RE = re.compile(
    r"(?ms)^--- BEGIN OPERATION FRAGMENT ---\n(.*?)\n--- END OPERATION FRAGMENT ---"
)


def _entries(pattern: re.Pattern[str], text: str) -> list[tuple[str, str]]:
    return [(path.strip(), fragment) for path, fragment in pattern.findall(text)]


def main() -> int:
    if not GUARD.is_file():
        print("GUARD CHECK FAILED: PROTECTED-LINE-GUARD is missing")
        return 1

    text = GUARD.read_text(encoding="utf-8")
    allowed = _entries(ALLOWED_RE, text)
    forbidden = _entries(FORBIDDEN_RE, text)
    operations = OPERATION_RE.findall(text)

    if not allowed:
        print("GUARD CHECK FAILED: no ALLOWED fragments found")
        return 1
    if not operations:
        print("GUARD CHECK FAILED: no OPERATION TABLE fragments found")
        return 1

    failures: list[str] = []

    for relative_path, fragment in allowed:
        target = ROOT / relative_path
        if not target.is_file():
            failures.append(f"{relative_path}: protected file is missing")
            continue
        actual = target.read_text(encoding="utf-8")
        if actual.count(fragment) != 1:
            failures.append(
                f"{relative_path}: ALLOWED fragment does not occur exactly once"
            )

    for relative_path, fragment in forbidden:
        target = ROOT / relative_path
        if not target.is_file():
            failures.append(f"{relative_path}: FORBIDDEN target file is missing")
            continue
        actual = target.read_text(encoding="utf-8")
        if actual.count(fragment) != 0:
            failures.append(
                f"{relative_path}: FORBIDDEN fragment is present in working file"
            )

    # Every operation fragment is forbidden until it is explicitly promoted
    # into ALLOWED by a later Guard change.
    protected_paths = sorted({path for path, _ in allowed} | {path for path, _ in forbidden})
    for fragment in operations:
        for relative_path in protected_paths:
            target = ROOT / relative_path
            if target.is_file() and target.read_text(encoding="utf-8").count(fragment):
                failures.append(
                    f"{relative_path}: OPERATION TABLE fragment is present before approval"
                )

    if failures:
        print("GUARD CHECK FAILED: protected-state invariant violated")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(
        f"GUARD CHECK PASSED: {len(allowed)} ALLOWED, "
        f"{len(forbidden)} FORBIDDEN, {len(operations)} OPERATION fragments"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
