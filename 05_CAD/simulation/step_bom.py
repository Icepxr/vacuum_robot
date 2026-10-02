"""Extract an occurrence-level BOM from an AP214/AP242 STEP assembly."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


def decode_step_string(value: str) -> str:
    """Decode STEP ``\\X2\\....\\X0\\`` UTF-16BE escapes."""

    def replace(match: re.Match[str]) -> str:
        raw = bytes.fromhex(match.group(1))
        return raw.decode("utf-16-be", errors="replace")

    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", replace, value)


def quoted_fields(value: str) -> list[str]:
    return [decode_step_string(item.replace("''", "'")) for item in re.findall(r"'((?:''|[^'])*)'", value)]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("step", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    text = args.step.read_text(encoding="utf-8", errors="replace")
    records = re.findall(
        r"#(\d+)\s*=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\((.*?)\);",
        text,
        flags=re.DOTALL,
    )
    occurrences: list[tuple[str, str]] = []
    for entity_id, body in records:
        fields = quoted_fields(body)
        if fields:
            occurrences.append((entity_id, fields[0]))

    counts = Counter(name.rsplit(":", 1)[0] for _, name in occurrences)
    output = args.output or args.step.with_name(args.step.stem + "_bom.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["occurrence_name", "quantity"])
        writer.writerows(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    print(f"Occurrences: {len(occurrences)}")
    print(f"BOM: {output}")
    for name, quantity in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{quantity:3d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
