"""Verify exact-content integrity of PROTECTED-LINE-GUARD."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "PROTECTED-LINE-GUARD"


_ENTRY_PATTERN = re.compile(
    r"(?ms)^FILE: (.+?)\n--- BEGIN ALLOWED ---\n(.*?)\n--- END ALLOWED ---"
)


def load_entries(text: str) -> list[tuple[str, str]]:
    """Parse protected file paths and exact authorized fragments."""
    return [(path.strip(), fragment) for path, fragment in _ENTRY_PATTERN.findall(text)]


def main() -> int:
    if not GUARD.is_file():
        print("GUARD CHECK FAILED: PROTECTED-LINE-GUARD is missing")
        return 1

    try:
        guard_text = GUARD.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"GUARD CHECK FAILED: cannot read guard: {exc}")
        return 1

    entries = load_entries(guard_text)
    if not entries:
        print("GUARD CHECK FAILED: no authorized fragments found")
        return 1

    failures: list[str] = []
    seen_paths: set[str] = set()

    for relative_path, fragment in entries:
        if relative_path in seen_paths:
            failures.append(f"{relative_path}: duplicate FILE entry")
            continue
        seen_paths.add(relative_path)

        target = ROOT / relative_path
        if not target.is_file():
            failures.append(f"{relative_path}: file is missing")
            continue

        try:
            actual = target.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"{relative_path}: cannot read file: {exc}")
            continue

        count = actual.count(fragment)
        if count != 1:
            failures.append(
                f"{relative_path}: authorized fragment occurrence count is {count}, expected exactly 1"
            )

    if failures:
        print("GUARD CHECK FAILED: protected working files differ from authorized content")
        for item in failures:
            print(f" - {item}")
        return 1

    print(f"GUARD CHECK PASSED: {len(entries)} authorized fragment(s) match exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
