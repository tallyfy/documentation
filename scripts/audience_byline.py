#!/usr/bin/env python3
"""
Idempotent audience-byline annotator for Tallyfy docs.

Adds `import { Audience } from "~/components";` + `<Audience to="ROLE" />` as the
first body element (right under the page title) of each file in a manifest. ROLE is
one of administrator | editor | guest (see the classification rules in CLAUDE.md,
"Role-based navigation" section - grounded in api-v2 permissions).

- Idempotent: a file that already contains `<Audience` is skipped (safe to re-run).
- Preserves frontmatter AND line endings byte-for-byte (these files have mixed LF
  body + CRLF auto-generated "Related articles" block; we must not churn it).
- Manifest format: one `ROLE<TAB>relative/path.mdx` per line (blank/`#` lines ignored).
  Re-derive the file list by grepping existing bylines (`rg -l '<Audience to=' ...`)
  or from the classification rules in CLAUDE.md.

Usage:
  python3 scripts/audience_byline.py --root . --manifest /path/to/role.tsv
  python3 scripts/audience_byline.py --root . --manifest /path/to/role.tsv --dry-run
"""
import argparse
import os
import re

AUD_IMPORT = 'import { Audience } from "~/components";'
FM_RE = re.compile(r'^(---\n.*?\n---\n)(.*)$', re.DOTALL)


def annotate(path, role, dry_run=False):
    # newline='' preserves original line endings byte-for-byte.
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    m = FM_RE.match(content)
    if not m:
        return 'error-no-frontmatter'
    fm, body = m.group(1), m.group(2)
    if re.search(r'<Audience\b', body):
        return 'skip-already'

    lines = body.split('\n')
    # Leading block = blank lines + top-level imports, up to the first real content line.
    idx = 0
    while idx < len(lines) and (lines[idx].strip() == '' or lines[idx].strip().startswith('import ')):
        idx += 1
    imports = [l for l in lines[:idx] if l.strip().startswith('import ')]
    rest = '\n'.join(lines[idx:]).lstrip('\n')

    if not any('Audience' in l for l in imports):
        imports.append(AUD_IMPORT)

    component = f'<Audience to="{role}" />'
    new_body = '\n' + '\n'.join(imports) + '\n\n' + component + '\n\n' + rest
    new_content = fm + new_body

    if not dry_run:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(new_content)
    return 'added'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='documentation repo root')
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    counts = {}
    with open(args.manifest, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            role, rel = line.split('\t')
            path = os.path.join(args.root, rel)
            if not os.path.isfile(path):
                print(f'MISSING  {rel}')
                counts['missing'] = counts.get('missing', 0) + 1
                continue
            result = annotate(path, role, args.dry_run)
            counts[result] = counts.get(result, 0) + 1
            print(f'{result:14} {role:13} {rel}')

    print('\nSummary:', ', '.join(f'{k}={v}' for k, v in counts.items() if v))


if __name__ == '__main__':
    main()
