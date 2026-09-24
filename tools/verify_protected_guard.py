"""Fail-closed verification for PROTECTED-LINE-GUARD."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "PROTECTED-LINE-GUARD"


def parse_guard(text: str):
    allowed = []
    forbidden = []
    operations = []

    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("FILE: "):
            relative_path = line[len("FILE: "):].rstrip("\r\n")
            index += 1
            if index >= len(lines):
                break

            marker = lines[index].rstrip("\r\n")
            if marker == "--- BEGIN ALLOWED ---":
                index += 1
                start = index
                while index < len(lines) and lines[index].rstrip("\r\n") != "--- END ALLOWED ---":
                    index += 1
                if index >= len(lines):
                    raise ValueError(f"unterminated ALLOWED block for {relative_path}")
                allowed.append((relative_path, "".join(lines[start:index])))
            elif marker == "--- BEGIN FORBIDDEN ---":
                index += 1
                start = index
                while index < len(lines) and lines[index].rstrip("\r\n") != "--- END FORBIDDEN ---":
                    index += 1
                if index >= len(lines):
                    raise ValueError(f"unterminated FORBIDDEN block for {relative_path}")
                forbidden.append((relative_path, "".join(lines[start:index])))
            else:
                raise ValueError(f"FILE {relative_path} has no ALLOWED/FORBIDDEN marker")
        elif line.rstrip("\r\n") == "--- BEGIN OPERATION FRAGMENT ---":
            index += 1
            start = index
            while index < len(lines) and lines[index].rstrip("\r\n") != "--- END OPERATION FRAGMENT ---":
                index += 1
            if index >= len(lines):
                raise ValueError("unterminated OPERATION FRAGMENT")
            operations.append("".join(lines[start:index]))
        index += 1

    return allowed, forbidden, operations


def main() -> int:
    if not GUARD.is_file():
        print("GUARD CHECK FAILED: PROTECTED-LINE-GUARD is missing")
        return 1

    try:
        guard_text = GUARD.read_text(encoding="utf-8")
        allowed, forbidden, operations = parse_guard(guard_text)
    except (OSError, ValueError) as exc:
        print(f"GUARD CHECK FAILED: cannot parse Guard: {exc}")
        return 1

    if not allowed:
        print("GUARD CHECK FAILED: no ALLOWED fragments found")
        return 1
    if not operations:
        print("GUARD CHECK FAILED: no OPERATION FRAGMENT found")
        return 1

    failures = []

    for relative_path, fragment in allowed:
        target = ROOT / relative_path
        if not target.is_file():
            failures.append(f"{relative_path}: protected file is missing")
            continue
        actual = target.read_text(encoding="utf-8")
        if actual.count(fragment) != 1:
            failures.append(
                f"{relative_path}: ALLOWED fragment occurrence count is "
                f"{actual.count(fragment)}, expected exactly 1"
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

    protected_paths = sorted(
        {path for path, _ in allowed} | {path for path, _ in forbidden}
    )
    for fragment in operations:
        for relative_path in protected_paths:
            target = ROOT / relative_path
            if target.is_file() and target.read_text(encoding="utf-8").count(fragment):
                failures.append(
                    f"{relative_path}: OPERATION FRAGMENT is present before approval"
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
