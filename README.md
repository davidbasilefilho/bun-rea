# bun-rea

Reverse engineering the bun runtime binary with [REA](https://github.com/morluto/rea) (Reverse Engineer Anything). This is a fun exercise, not a security audit.

**Status: in progress.** The static inventory is done. The Ghidra-backed decompilation is still running, and the sections on it below will be filled in when it finishes.

## Target

| Field | Value |
| --- | --- |
| Binary | `/root/.bun/bin/bun` (copied to a scratch directory; not committed) |
| Version | `bun --revision` → `1.4.2+744846f84` |
| SHA-256 | `a83d263767d839e4d2649ca8e35d07159c7afc99afdc96d731ced29e056dda0c` |
| Size | 79,500,640 bytes (75.82 MiB) |
| Format | ELF64, `EXEC`, x86-64, `HAS_SYMS`, entry point `0x177a800` |
| Dynamic deps | `libc.so.6`, `libm.so.6`, `libpthread.so.0`, `libdl.so.2`, `ld-linux-x86-64.so.2` |

Everything else bun needs is linked into the binary. The only things it asks the system for are glibc, libm, and the loader.

## Tooling

- REA CLI `rea-agents@6.5.0` (npm), run from a scratch install.
- Ghidra 12.1.4 PUBLIC, the version REA's own CI pins. The zip's SHA-256 matches the pin (`ddac49f9…d4db`).
- JDK 21 (`openjdk 21.0.12.1`), Node 22.22.0.
- GNU objdump and readelf for cross-checks.

REA's native analysis needs a provider. Ghidra is the only one installed, so it is the only one used.

## Static findings

These come from REA's objdump adapter and from `readelf`/`objcopy` on the same file. Each claim is backed by a file in `evidence/`.

### Sections

| Section | Size | Notes |
| --- | --- | --- |
| `.text` | 56,841,267 B (54.21 MiB) | Almost all code. |
| `.rodata` | 19,795,444 B (18.88 MiB) | |
| `.bun_builtins` | 2,614,191 B (2.49 MiB) | Custom section. See below. |
| `.bun` | 8 B | Custom section. Not analyzed yet. |
| `__DATA,__wtf_config` | 16 KiB | Mach-O-style name in an ELF file. |
| `__DATA,__jsc_opcodes` | 16 KiB | Mach-O-style name in an ELF file. |
| `.bss` | 1,806,760 B (1.72 MiB) | |

Sections named `__DATA,__wtf_config` and `__DATA,__jsc_opcodes` look like they come from a JavaScriptCore/WebKit build, but the symbols themselves are absent (see below). I'm treating the JSC link as a hypothesis until Ghidra confirms it.

### Symbol table

The `.symtab` holds only 1,075 entries, which is small for a binary this size.

| Family (by symbol prefix) | Count |
| --- | --- |
| `_ZN2v8…` (V8 C++ API) | 119 |
| `uv_…` (libuv) | 316 |
| `napi_…` (Node-API) | 149 |
| `ZSTD_…` (zstd) | 4 |
| `Bun`/`bun`-named | 0 |
| C++ standard library (`_ZNSt`/`_ZSt`) | 0 |

Of the 1,075 entries, 676 are defined in `.text`, 394 are undefined (imports), and 5 are in `.bss`.

The table has no JavaScriptCore, WTF, or BoringSSL names, even though the config sections for JSC/WTF are present. My working hypothesis is that bun exports only the ABI surface native addons link against (V8, libuv, and N-API) and strips the rest. That is consistent with the table but not proven. The Ghidra run should show whether those internals exist in `.text` without names.

### The embedded builtins (`.bun_builtins`)

- The section begins with the 8-byte magic `BUNBLTNS`. The next `u32` is `version = 1`. The `u32` at offset 16 is `0xc5` = 197, which I read as the module count. The field at offset 12 (`0xf7d0d4e1`) is not identified yet.
- The module bodies are plaintext JavaScript. They use `@`-prefixed calls such as `@createCommonJSModule`, `@requireMap.@set`, and `@makeErrorWithCode`. That is JavaScriptCore's builtin convention, which is evidence for the JSC hypothesis above.
- Module names visible in the blob include `bun:test`, `bun:sqlite`, `bun:sql`, `node:tls`, `node:http`, `node:stream/iter`, and `node:zlib/iter`.
- I have **not** yet decoded the full 197-entry name table. My first attempts at a simple layout failed, so I'm waiting on Ghidra to show the loader code that reads it.

### Build and debug info

- `file` reports the binary as not stripped, but the `.symtab` is small (see above).
- Ghidra's log reports no DWARF information in the binary.

## REA results

| Operation | Result |
| --- | --- |
| `inspect-artifact` | Evidence recorded. Format `elf`, SHA-256 matches. Next step suggested: open a native provider. |
| `inspect-with-objdump file_headers / section_headers / symbols` | Evidence recorded. Artifact SHA-256 unchanged before and after each run. |
| `inspect-binary-layout` | **Refused.** The file is 79.5 MB and REA's limit is 32 MiB (33,554,432 B). I did not work around this. |
| `analyze --provider ghidra` (attempt 1) | **Timed out.** Ghidra's import and auto-analysis did not finish in REA's 45-minute startup deadline (`provider_timeout`). |
| `analyze --provider ghidra` (attempt 2) | Running, with a 3-hour startup deadline and "Decompiler Switch Analysis" disabled. The log showed that analyzer restarting repeatedly in attempt 1. |

Decompilation, function-level analysis, string search, and cross-references are pending on attempt 2.

## Limits and scope

- No bun or WebKit source was consulted. Every claim above comes from the binary and from tool output.
- The binary is not committed. Only derived evidence is.
- REA's `inspect-binary-layout` cannot run on a file this size, so ELF layout here comes from `objdump` and `readelf`, not REA.

## Reproduce

```bash
# REA CLI (scratch install)
npm install rea-agents@6.5.0

# Ghidra 12.1.4 (the URL and SHA-256 are pinned in REA's .github/workflows/ghidra-bridge-sources.yml)
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC

rea inspect-artifact ./bun --format json
rea inspect-with-objdump ./bun file_headers
rea inspect-with-objdump ./bun section_headers
rea inspect-with-objdump ./bun symbols
python3 scripts/symtab_families.py evidence/rea-objdump-symbols.txt
```

## Evidence

- `evidence/rea-inspect-artifact.json`: artifact-level inspection.
- `evidence/rea-objdump-file-headers.json`, `evidence/rea-objdump-section-headers.json`: ELF headers and sections.
- `evidence/rea-objdump-symbols.txt`: the raw symbol table.
- `evidence/rea-inspect-binary-layout-refusal.json`: the 32 MiB refusal.
- `evidence/rea-analyze-attempt1-timeout.json`: the first Ghidra timeout, trimmed.
- `scripts/symtab_families.py`: symbol counts by section and family.
