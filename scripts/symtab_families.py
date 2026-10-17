"""Count symbol-table entries by section and by library family.

Usage: python3 scripts/symtab_families.py evidence/rea-objdump-symbols.txt

Input is the stdout of `objdump -t` as captured by REA's inspect-with-objdump
(`symbols` operation).
"""
import collections
import re
import sys

rows = []
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    if "\t" not in line:
        continue
    left, right = line.split("\t", 1)
    fields = left.split()
    if len(fields) < 2:
        continue
    section = fields[-1]
    name_parts = right.split()
    name = name_parts[-1] if name_parts else ""
    kind = "F" if " F " in left or left.endswith(" F") else ("O" if " O " in left else "-")
    rows.append((section, kind, name))

print("parsed symbol rows:", len(rows))
print("by section:", collections.Counter(r[0] for r in rows).most_common(8))
print("by kind:", dict(collections.Counter(r[1] for r in rows)))

families = [
    ("V8 C++ API (_ZN2v8)", r"^_ZN2v8"),
    ("libuv (uv_)", r"^uv_"),
    ("N-API (napi_)", r"^napi_"),
    ("zstd (ZSTD_)", r"^ZSTD_"),
    ("Bun/bun-named", r"[Bb]un"),
    ("C++ std (_ZNSt/_ZSt)", r"^_Z(NS|S)t"),
    ("other C++ mangled (_ZN)", r"^_ZN"),
    ("glibc/runtime misc", r"^(__libc|_dl_|__cxa)"),
]
for label, pattern in families:
    rx = re.compile(pattern)
    hits = [r[2] for r in rows if rx.search(r[2])]
    print(f"{label:<26} {len(hits):>5}   e.g. {hits[:2]}")
