#!/usr/bin/env bash
#
# Validate every D2 diagram in the documentation.
#
# Two things are checked per fence:
#   1. it COMPILES, using the same D2 flags the site build uses;
#   2. every colour it emits is in the Tallyfy house palette.
#
# The palette check exists because a diagram using an off-palette colour
# compiles perfectly and renders correctly in light mode, then becomes
# invisible or off-brand in dark mode with nothing going red. Compilation
# alone cannot see that class of defect.
#
# Usage:
#   scripts/validate-d2.sh                  compile + palette, honouring the baseline
#   scripts/validate-d2.sh --strict         ignore the baseline; report ALL palette debt
#   scripts/validate-d2.sh --write-baseline regenerate the baseline from the tree
#
# Exit codes:
#   0  all diagrams compile and are on-palette (or baselined)
#   1  findings
#   2  the gate could not run (no d2, no python3, no diagrams found)
#
# Exit 2 on "no diagrams found" is deliberate. A sweep that discovers nothing
# satisfies every assertion made about it, so a zero-fence result is a broken
# gate rather than a clean tree.
#
# ---------------------------------------------------------------------------
# Why this script is shaped the way it is (tallyfy/documentation#192)
#
# The previous version could never fail. Its `while` loop was fed by a pipe,
# and under bash - which its own shebang selected - a piped loop body runs in a
# SUBSHELL, so every `error_count` increment was discarded and the script always
# exited 0. Measured, on the same one-line loop:
#
#     bash -> error_count in parent: 0     (the shebang; ALWAYS exits 0)
#     zsh  -> error_count in parent: 3     (this Mac's interactive shell)
#
# zsh runs the last pipeline stage in the current shell; bash forks it. So
# pasting the old script into a terminal gave the right answer and running it as
# a script did not. Every loop below is therefore fed by PROCESS SUBSTITUTION
# (`done < <(...)`), which keeps the body in the current shell, and never by a
# pipe.
#
# Written for bash 3.2, which is what macOS ships, so no associative arrays.
# ---------------------------------------------------------------------------

# No `set -e`: findings must accumulate, not abort the sweep on the first one.
set -uo pipefail

# --- The Tallyfy house palette ----------------------------------------------
# D2-DIAGRAMS.md is the source of truth and states this as MANDATORY: "Use ONLY
# these colors in D2 diagrams. Random colors are forbidden." This gate is what
# makes that rule enforceable rather than aspirational.
#   #225930  border / all strokes
#   #f2faf4  primary fill
#   #e1f7e6  secondary fill
#   #fff3cd  warning / reminder
#
# D2-DIAGRAMS.md also documents a DARK theme palette (#0D0D0D, #0b2813, and
# #e1f7e6 as a border). No diagram in the corpus hardcodes those - dark mode is
# produced by D2's own --dark-theme, so authors write the light colours only. If
# a diagram ever legitimately needs a dark literal, add it here and say why.
PALETTE="#225930 #f2faf4 #e1f7e6 #fff3cd"

# --- The D2 flags the site build uses ---------------------------------------
# Read from tallyfy/support-docs astro.config.mjs (the `d2({...})` block) and
# astro-d2's own libs/d2.ts, which assembles the command line as:
#
#   d2 --layout=<layout> --theme=<theme.default> --sketch=<sketch> \
#      --pad=<pad> --dark-theme=<theme.dark> - <outputPath>
#
# `--force-appendix` is NOT passed because the config sets `appendix: false`,
# and no --font-* flags are passed because the config sets no `fonts`.
#
# NOTE the dark theme is 8, not 200. The previous script validated at
# --dark-theme=200, so it could pass what the build fails.
D2_LAYOUT="elk"
D2_THEME="104"
D2_SKETCH="false"
D2_PAD="10"
D2_DARK_THEME="8"

MODE="baseline"
for arg in "$@"; do
    case "$arg" in
        --strict)         MODE="strict" ;;
        --write-baseline) MODE="write" ;;
        -h|--help)        sed -n '2,28p' "$0"; exit 0 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

# --- Locate the repo, so the script works from any cwd ----------------------
# The previous script used a relative path in its outer grep, so it only worked
# when invoked from the repo root.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCS_DIR="${REPO_ROOT}/src/content/docs"
BASELINE_FILE="${SCRIPT_DIR}/d2-palette-baseline.txt"

echo "Validating D2 diagrams"
echo "  repo:  ${REPO_ROOT}"
echo "  mode:  ${MODE}"
echo "  flags: --layout=${D2_LAYOUT} --theme=${D2_THEME} --sketch=${D2_SKETCH} --pad=${D2_PAD} --dark-theme=${D2_DARK_THEME}"
echo ""

# --- Preflight. Anything missing here is exit 2, never a pass. --------------
if ! command -v d2 >/dev/null 2>&1; then
    echo "CANNOT RUN: d2 is not installed. Install it with: brew install d2"
    exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "CANNOT RUN: python3 is not available (needed for the palette check)."
    exit 2
fi

if [ ! -d "$DOCS_DIR" ]; then
    echo "CANNOT RUN: docs directory not found at ${DOCS_DIR}"
    exit 2
fi

echo "d2 version: $(d2 --version 2>&1)"
echo ""

WORK_DIR="$(mktemp -d)" || { echo "CANNOT RUN: mktemp failed."; exit 2; }
trap 'rm -rf "$WORK_DIR"' EXIT

# The palette checker. Reads one SVG, prints one offending colour per line.
#
# It strips <style> and <mask> regions BEFORE scanning, and that is the whole
# design:
#   - <style> holds D2's own theme colours (32 hexes for theme 104 + dark 8).
#     A diagram that sets no colours of its own emits ZERO hex literals outside
#     <style>, so stripping it leaves exactly the author-chosen colours.
#   - <mask> is built from fill="white" and fill="black" on every diagram.
#     Those are structural, not palette.
#
# Note it does NOT skip elements that carry a class. D2 puts class="shape" and
# class="connection" on author-styled elements too, so skipping classed
# elements would blind the check to the author's own fills. Measured: an
# author-filled ellipse carries class="shape" and the arrowhead marker that
# inherits the connection colour carries class="connection".
PALETTE_PY="${WORK_DIR}/palette_check.py"
cat > "$PALETTE_PY" <<'PYEOF'
import re, sys

ALLOWED = {c.strip().lower() for c in sys.argv[2].split() if c.strip()}
# Structural non-colours D2 legitimately emits outside <style> and <mask>.
STRUCTURAL_NAMES = {"none", "transparent", "inherit", "currentcolor"}

svg = open(sys.argv[1], encoding="utf-8").read()

# Strip the regions whose colours are not the author's choice.
svg = re.sub(r"<style\b[^>]*>.*?</style>", " ", svg, flags=re.S | re.I)
svg = re.sub(r"<mask\b[^>]*>.*?</mask>", " ", svg, flags=re.S | re.I)

def norm(h):
    h = h.lower()
    if len(h) == 4:  # #abc -> #aabbcc
        return "#" + "".join(ch * 2 for ch in h[1:])
    if len(h) == 9:  # #rrggbbaa -> compare on the rgb part
        return h[:7]
    return h

offenders = []

# Hex literals in any colour-bearing attribute.
for m in re.finditer(r'\b(fill|stroke|stop-color|flood-color|color)="(#[0-9A-Fa-f]{3,8})"', svg):
    v = norm(m.group(2))
    if v not in ALLOWED:
        offenders.append(f"{m.group(1)}={m.group(2)}")

# Named colours are just as dangerous in dark mode as an off-palette hex, so
# flag any that survive the strip above.
for m in re.finditer(r'\b(fill|stroke|stop-color|flood-color|color)="([A-Za-z]+)"', svg):
    if m.group(2).lower() not in STRUCTURAL_NAMES:
        offenders.append(f"{m.group(1)}={m.group(2)}")

for o in sorted(set(offenders)):
    print(o)
PYEOF

total_files=0
total_fences=0
compile_failures=0
palette_failures=0
baselined_hits=0

findings_file="${WORK_DIR}/findings.txt"
seen_baseline="${WORK_DIR}/seen_baseline.txt"
new_baseline="${WORK_DIR}/new_baseline.txt"
: > "$findings_file"
: > "$seen_baseline"
: > "$new_baseline"

# --- Walk every .mdx file ---------------------------------------------------
# -print0 / read -d '' so a filename containing a space or a glob character is
# handled correctly. The previous script used an unquoted $(grep -l ...), which
# word-split on whitespace.
while IFS= read -r -d '' file; do
    # Cheap skip for files with no diagrams.
    if ! /usr/bin/grep -q '^```d2[[:space:]]*$' "$file"; then
        continue
    fi

    rel="${file#"${REPO_ROOT}/"}"
    total_files=$((total_files + 1))

    # Split this file's fences into separate .d2 files, and record the line
    # number each fence starts on so a finding can name it.
    manifest="${WORK_DIR}/manifest.tsv"
    : > "$manifest"
    awk -v outdir="$WORK_DIR" -v manifest="$manifest" '
        /^```d2[[:space:]]*$/ && !inblock {
            inblock = 1; n++; startline = NR + 1
            out = sprintf("%s/fence_%03d.d2", outdir, n)
            printf "" > out
            next
        }
        inblock && /^```[[:space:]]*$/ {
            inblock = 0
            close(out)
            printf "%d\t%d\t%s\n", n, startline, out >> manifest
            next
        }
        inblock { print >> out }
    ' "$file"

    # Process substitution, NOT a pipe: the counters below must survive.
    while IFS=$'\t' read -r fence_num start_line fence_path; do
        [ -n "${fence_num:-}" ] || continue
        total_fences=$((total_fences + 1))

        svg_out="${WORK_DIR}/fence_${fence_num}.svg"
        d2_err="${WORK_DIR}/fence_${fence_num}.err"

        # Same invocation shape as the build: source on stdin via `-`.
        d2 "--layout=${D2_LAYOUT}" "--theme=${D2_THEME}" \
           "--sketch=${D2_SKETCH}" "--pad=${D2_PAD}" \
           "--dark-theme=${D2_DARK_THEME}" \
           - "$svg_out" < "$fence_path" > "$d2_err" 2>&1
        d2_rc=$?

        if [ "$d2_rc" -ne 0 ]; then
            compile_failures=$((compile_failures + 1))
            {
                echo "COMPILE FAILED  ${rel}  fence #${fence_num} (line ${start_line})"
                sed 's/^/                /' "$d2_err" | head -8
            } >> "$findings_file"
            continue
        fi

        # Compiled fine. Now the check compilation cannot make.
        bad="$(python3 "$PALETTE_PY" "$svg_out" "$PALETTE" 2>/dev/null)"
        [ -n "$bad" ] || continue

        key="${rel}"$'\t'"${fence_num}"
        printf '%s\n' "$key" >> "$new_baseline"

        if [ "$MODE" = "baseline" ] && [ -f "$BASELINE_FILE" ] \
           && /usr/bin/grep -qxF "$key" "$BASELINE_FILE"; then
            baselined_hits=$((baselined_hits + 1))
            printf '%s\n' "$key" >> "$seen_baseline"
            continue
        fi

        palette_failures=$((palette_failures + 1))
        {
            echo "OFF-PALETTE     ${rel}  fence #${fence_num} (line ${start_line})"
            while IFS= read -r c; do
                [ -n "$c" ] && echo "                ${c}"
            done < <(printf '%s\n' "$bad")
            echo "                allowed: ${PALETTE}"
        } >> "$findings_file"
    done < <(cat "$manifest")
done < <(find "$DOCS_DIR" -type f -name '*.mdx' -print0)

# --- Zero-fence floor -------------------------------------------------------
if [ "$total_fences" -eq 0 ]; then
    echo "CANNOT RUN: discovered 0 D2 fences under ${DOCS_DIR}."
    echo "A sweep that finds nothing satisfies every assertion made about it,"
    echo "so this is a broken gate rather than a clean tree."
    exit 2
fi

if [ "$MODE" = "write" ]; then
    {
        echo "# D2 palette baseline - tallyfy/documentation#192"
        echo "#"
        echo "# Diagrams that already used off-palette colours when the palette check"
        echo "# was introduced. One '<path>\\t<fence number>' per line."
        echo "#"
        echo "# This is a RATCHET, not an allowance. A NEW off-palette diagram fails"
        echo "# the gate. An entry here whose diagram has since been fixed ALSO fails"
        echo "# the gate, telling you to delete the line, so the list can only shrink."
        echo "#"
        echo "# See the whole list with: scripts/validate-d2.sh --strict"
        echo "# Regenerate with:         scripts/validate-d2.sh --write-baseline"
        sort "$new_baseline"
    } > "$BASELINE_FILE"
    echo "Wrote baseline: ${BASELINE_FILE}"
    echo "  entries: $(/usr/bin/grep -cv '^#' "$BASELINE_FILE")"
    exit 0
fi

echo "Checked ${total_fences} D2 fences across ${total_files} files."
echo ""

# --- Rot detector -----------------------------------------------------------
# A baseline entry that no longer has a violation is dead allowance. Left
# alone it would silently re-admit that diagram later, which is exactly how a
# baseline stops being a ratchet. So a stale entry is a hard failure.
stale_count=0
if [ "$MODE" = "baseline" ] && [ -f "$BASELINE_FILE" ]; then
    while IFS= read -r line; do
        case "$line" in ''|'#'*) continue ;; esac
        if ! /usr/bin/grep -qxF "$line" "$new_baseline"; then
            stale_count=$((stale_count + 1))
            {
                echo "STALE BASELINE  ${line}"
                echo "                this diagram is on-palette now. Delete the line from"
                echo "                scripts/d2-palette-baseline.txt"
            } >> "$findings_file"
        fi
    done < <(cat "$BASELINE_FILE")
fi

if [ -s "$findings_file" ]; then
    echo "FINDINGS"
    echo ""
    cat "$findings_file"
    echo ""
    echo "  compile failures: ${compile_failures}"
    echo "  off-palette:      ${palette_failures}"
    echo "  stale baseline:   ${stale_count}"
    [ "$baselined_hits" -gt 0 ] && echo "  known debt:       ${baselined_hits} (baselined)"
    exit 1
fi

echo "All ${total_fences} diagrams compile."
if [ "$baselined_hits" -gt 0 ]; then
    echo "${baselined_hits} carry known off-palette debt (see scripts/d2-palette-baseline.txt)."
    echo "Run with --strict to see them."
fi
echo "No new findings."
exit 0
