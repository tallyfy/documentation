#!/usr/bin/env python3
"""
Publish the screenshots committed under screenshots/launchbrightly/ and record them in
documentation_assets.csv (tallyfy/documentation#464).

  ingest    Run by the pipeline on staging. Every image under screenshots/ that git tracks is
            checked against repo_screenshot_rules.py, uploaded to R2 under a content-hashed key
            when it is not there yet, read back from screenshots.tallyfy.com and compared by
            SHA-256, and given a row in the CSV (source=launchbrightly, keyed by repo_path).
            It never deletes anything from R2. Any problem stops it before the CSV is written,
            so staging is left as it was: a file that is not an allowed image or sidecar, an
            article linking a /screenshots/ path that is not an accepted image in the tree, a
            failed upload or read-back, or any commit to the CSV authored by LaunchBrightly.
            When nothing changed it writes nothing, so the pipeline has nothing to commit.
            --dry-run makes no network call and writes nothing; it prints the rows it would write.
  verify    Run by the pipeline on main, with no credentials. Every linked image must be in the
            tree and have a row whose content_sha256, r2_key and production_url match its
            bytes. --online also downloads each one from its public URL and compares the hash.
  --self-test
            Every rule, red and green, on scratch git repositories with a fake R2. No network,
            no credentials, and never the real CSV.

The upload goes through R2's S3-compatible API with boto3, because the Cloudflare REST objects
API that r2_uploader.py uses refuses a token scoped to one bucket (measured 2026-11-06: 403 on
get, head and list of `screenshots`), and the S3 API honours that scope. The credentials come
from R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and CLOUDFLARE_ACCOUNT_ID, which the pipeline hands
to the ingest step alone. boto3 is imported only when an upload is needed, so this module and
its self-test run without it.

Exit codes: 0 done or nothing to do, 1 refused or failed (the CSV is not written), 2 could not run.
"""

import argparse
import contextlib
import csv
import hashlib
import io
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import repo_screenshot_rules as rules
from asset_inventory import AssetInventory
from audit_sync import _frontmatter_id

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_NAME = "documentation_assets.csv"
DOCS = "src/content/docs"
BUCKET = "screenshots"
CACHE_CONTROL = "public, max-age=31536000, immutable"
SECRET_NAMES = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID")
CAPTION_COLUMNS = ("ai_caption_alt", "ai_caption_descriptive", "ai_caption_seo")
# Cleared when an image's bytes change, unless its sidecar gives a new value: they described
# the old image (the #469 review found replace kept stale provenance).
PROVENANCE_CLEARED_ON_CHANGE = ("captured_at", "source_description", "source_ref", "app_url")
# Sidecar key -> CSV column, for the columns a sidecar fills directly.
SIDECAR_COLUMNS = {"app_url": "app_url", "captured_at": "captured_at",
                   "description": "source_description", "recipe_id": "source_ref"}

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


class CannotRun(Exception):
    """The script could not do its job. Exit 2, never a pass."""


def log(msg=""):
    print(msg, flush=True)


def annotate(level, msg):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _git(repo, *args, binary=False):
    # Literal pathspecs, so a path is never read as a glob or as pathspec magic.
    env = dict(os.environ, GIT_LITERAL_PATHSPECS="1")
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, env=env)
    if proc.returncode != 0:
        raise CannotRun(f"git {' '.join(args[:2])} failed: "
                        f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout if binary else proc.stdout.decode("utf-8", "surrogateescape")


# ---------------------------------------------------------------------------------------
# reading the repository


def tracked_files(repo):
    """{path: (mode, blob sha)} for every file git tracks under screenshots/."""
    out = _git(repo, "ls-files", "-s", "-z", "--", rules.REPO_FOLDER)
    files = {}
    for record in out.split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        mode, blob, _stage = meta.split()
        files[path] = (mode, blob)
    return files


def blob_reader(repo, blob):
    return lambda: _git(repo, "cat-file", "blob", blob, binary=True)


def lb_csv_commits(repo):
    """Commits to the CSV that LaunchBrightly authored or committed. Its pull requests may not
    touch the file (scripts/lb-pr-guard.py refuses them), so any such commit means a guard
    was passed by and the rows cannot be trusted."""
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() != "false":
        raise CannotRun("this checkout is shallow, so the CSV's history cannot be read. "
                        "Check out with fetch-depth: 0.")
    out = _git(repo, "log", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce", "--", CSV_NAME)
    found = []
    for line in out.splitlines():
        sha, *people = line.split("\x1f")
        if any("launchbrightly[bot]" in p.lower() for p in people):
            found.append(f"{sha[:12]} ({people[0]} <{people[1]}>)")
    return found


def _slug(rel):
    """An article's path slug, the form article_ids uses when a page has no frontmatter id."""
    inner = rel[len(DOCS) + 1:] if rel.startswith(DOCS + "/") else rel
    return re.sub(r"\.mdx?$", "", inner).replace("/", "-")


def _frontmatter_title(text):
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    m = _TITLE_RE.search(text[:end] if end != -1 else "")
    if not m:
        return ""
    title = m.group(1)
    if len(title) >= 2 and title[0] == title[-1] and title[0] in "\"'":
        title = title[1:-1]
    return title.strip()


def _clean_heading(text):
    text = re.sub(r"\s*\{#[^}]*\}\s*$", "", text)
    return re.sub(r"[*`]", "", text).strip()


def scan_docs(repo):
    """(usage, refs). usage: {repo path: {'pages', 'alt', 'screen'}}; refs: [(path, file, line)].

    Pages are read in sorted path order, so 'the first page that uses it' is stable. alt is the
    first non-empty alt text an article gives the image; screen is the first page's title plus
    the nearest heading above the image."""
    docs = repo / DOCS
    if not docs.is_dir():
        raise CannotRun(f"no {DOCS} folder in {repo}")
    usage, refs = {}, []
    for path in sorted(list(docs.rglob("*.mdx")) + list(docs.rglob("*.md"))):
        text = path.read_text(encoding="utf-8", errors="replace")
        found = rules.find_references(text)
        if not found:
            continue
        rel = path.relative_to(repo).as_posix()
        page = _frontmatter_id(text) or _slug(rel)
        title = _frontmatter_title(text)
        headings = [(n, _clean_heading(m.group(1))) for n, line in rules.lines_outside_fences(text)
                    for m in [_HEADING_RE.match(line)] if m]
        for ref_path, number, alt in found:
            refs.append((ref_path, rel, number))
            entry = usage.setdefault(ref_path, {"pages": set(), "alt": None, "screen": None})
            entry["pages"].add(page)
            if entry["alt"] is None and alt:
                entry["alt"] = alt
            if entry["screen"] is None:
                above = [h for n, h in headings if n < number]
                entry["screen"] = ", ".join(x for x in (title, above[-1] if above else "") if x)
    return usage, refs


# ---------------------------------------------------------------------------------------
# R2 through its S3-compatible API


def _is_not_found(exc):
    """True when a boto3 error says the object does not exist. Read from the error's response
    rather than its class, so this module does not need botocore to recognise it."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = str((response.get("Error") or {}).get("Code", ""))
    status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    return status == 404 or code in ("404", "NoSuchKey", "NotFound")


class S3Uploader:
    """Checks for and uploads objects in the screenshots bucket. It has no delete, on purpose."""

    def __init__(self, client, bucket=BUCKET):
        self.client = client
        self.bucket = bucket

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        missing = [name for name in SECRET_NAMES if not env.get(name)]
        if missing:
            raise CannotRun(f"cannot upload: {', '.join(missing)} not set. The pipeline hands these "
                            f"from the r2-screenshots environment to the ingest step only.")
        account = env["CLOUDFLARE_ACCOUNT_ID"].strip()
        if not re.fullmatch(r"[0-9a-f]{32}", account):
            raise CannotRun("CLOUDFLARE_ACCOUNT_ID is not 32 lower-case hex characters")
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise CannotRun("boto3 is not installed (python -m pip install boto3)")
        kwargs = {}
        try:
            # boto3 1.36 began adding checksum headers by default; ask for them only where an
            # operation requires one, as Cloudflare's R2 boto3 guide does.
            kwargs["config"] = Config(request_checksum_calculation="when_required",
                                      response_checksum_validation="when_required")
        except TypeError:
            pass  # an older botocore, which never added them
        client = boto3.client("s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                              aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                              aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
                              region_name="auto", **kwargs)
        return cls(client)

    def head(self, key):
        """{'etag', 'size'} when the object exists, None when R2 says 404. Any other error raises."""
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - botocore's ClientError, judged by its response
            if _is_not_found(exc):
                return None
            raise
        return {"etag": str(resp.get("ETag", "")).strip('"'), "size": resp.get("ContentLength")}

    def put(self, key, body, content_type, cache_control):
        resp = self.client.put_object(Bucket=self.bucket, Key=key, Body=body,
                                      ContentType=content_type, CacheControl=cache_control)
        return {"etag": str(resp.get("ETag", "")).strip('"')}


def http_fetch(url, attempts=4, pause=5.0):
    """The bytes at a public URL, or None after `attempts` tries."""
    import requests
    last = ""
    for attempt in range(attempts):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.content
            last = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last = repr(exc)
        if attempt < attempts - 1:
            time.sleep(pause)
    log(f"  could not read {url}: {last}")
    return None


# ---------------------------------------------------------------------------------------
# ingest and verify


def _format_bytes(n):
    return AssetInventory._format_bytes(n)


def _rows_by_repo_path(rows, problems):
    index = {}
    for i, row in enumerate(rows):
        rp = rules.normalize_ref(row.get("repo_path") or "")
        if not rp:
            continue
        if rp in index:
            problems.append(f"{CSV_NAME} has more than one row with repo_path {rp}")
        index[rp] = i
    return index


def _check_inputs(repo):
    """(tree report, usage, refs, problems) shared by ingest and verify."""
    tracked = tracked_files(repo)
    report = rules.check_tree({p: (mode, blob_reader(repo, blob)) for p, (mode, blob) in tracked.items()})
    problems = list(report.problems)
    for notice in report.notices:
        log(f"NOTICE: {notice}")
    usage, refs = scan_docs(repo)
    accepted = {rules.repo_path(p) for p in report.images}
    present = {rules.repo_path(p) for p in tracked}
    for ref_path, rel, line in refs:
        if ref_path not in accepted:
            why = ("is not an accepted image (see the problems above)" if ref_path in present
                   else "is not in the repository")
            problems.append(f"{rel}:{line} links {ref_path}, which {why}")
    return report, usage, refs, problems


def _new_row(inventory, old, rel, data, digest, key, usage, sidecar, etag, now_iso):
    rp = rules.repo_path(rel)
    base = dict(old) if old is not None else inventory._fill_defaults(
        {"r2_key": key, "source": "launchbrightly"})
    changed = old is not None and (old.get("content_sha256") or "") != digest
    key_changed = old is None or old.get("r2_key") != key
    use = usage.get(rp)
    pages = sorted(use["pages"]) if use else []
    row = base
    row.update({
        "filename": PurePosixPath(key).name,
        "r2_key": key,
        "production_url": rules.public_url(key),
        "source_type": "native" if pages else "orphaned",
        "file_type": "." + rules.extension(rel),
        "file_size": _format_bytes(len(data)),
        "file_size_bytes": str(len(data)),
        "url_exists": "True",
        "article_ids": ",".join(pages),
        "article_count": str(len(pages)),
        "source": "launchbrightly",
        "repo_path": rp,
        "content_sha256": digest,
        "markdown_alt": (use["alt"] or "") if use else "",
    })
    if key_changed:
        row["last_modified"] = now_iso
        row["etag"] = etag or ""
    elif etag:
        row["etag"] = etag
    if old is None or changed:
        for column in CAPTION_COLUMNS:
            row[column] = ""
        row["needs_caption"] = "yes"
    if changed:
        for column in PROVENANCE_CLEARED_ON_CHANGE:
            row[column] = ""
    sidecar = sidecar or {}
    for key_name, column in SIDECAR_COLUMNS.items():
        if sidecar.get(key_name):
            row[column] = sidecar[key_name]
    screen = sidecar.get("screen") or sidecar.get("title")
    if screen:
        row["app_screen"], row["location_source"] = screen, "launchbrightly"
    elif old is not None and not changed and old.get("location_source") == "launchbrightly":
        pass  # LaunchBrightly said where it was taken, and the image has not changed
    else:
        row["app_screen"] = (use["screen"] or "") if use else ""
        row["location_source"] = "inferred"
    return row


def ingest(repo, inventory, make_uploader, fetch, dry_run=False, now=None):
    repo = Path(repo)
    lb = lb_csv_commits(repo)
    if lb:
        msg = (f"REFUSED: {CSV_NAME} has {len(lb)} commit(s) authored or committed by LaunchBrightly "
               f"({', '.join(lb)}). Its pull requests may not touch the inventory, so these rows "
               f"cannot be trusted. A person must review and revert them before this job runs again.")
        log(msg)
        annotate("error", msg)
        return 1
    report, usage, refs, problems = _check_inputs(repo)
    rows = inventory.read_inventory()
    before = [dict(r) for r in rows]
    by_rp = _rows_by_repo_path(rows, problems)
    if problems:
        return _refuse(problems, "nothing was uploaded")

    now_iso = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    uploader = None
    planned, uploaded = [], []
    for rel in sorted(report.images):
        data = report.images[rel]
        digest = sha256(data)
        key = rules.derive_key(rel, digest)
        url = rules.public_url(key)
        rp = rules.repo_path(rel)
        idx = by_rp.get(rp)
        old = rows[idx] if idx is not None else None
        clash = [r.get("repo_path") or r.get("production_url") for j, r in enumerate(rows)
                 if j != idx and r.get("r2_key") == key]
        if clash:
            problems.append(f"{rp}: another row already uses the key {key} ({', '.join(clash)})")
            continue
        settled = (old is not None and old.get("r2_key") == key
                   and old.get("content_sha256") == digest and old.get("url_exists") == "True")
        etag = None
        if not settled:
            if dry_run:
                planned.append(f"{rp}: would look for {key} on R2, upload it if missing "
                               f"({rules.content_type(rel)}, Cache-Control: {CACHE_CONTROL}), "
                               f"and read {url} back")
            else:
                if uploader is None:
                    uploader = make_uploader()
                try:
                    info = uploader.head(key)
                    if info is not None:
                        etag = info.get("etag")
                        log(f"{rp}: {key} is already on R2; not uploading it again")
                    else:
                        etag = uploader.put(key, data, rules.content_type(rel), CACHE_CONTROL).get("etag")
                        uploaded.append(key)
                        log(f"{rp}: uploaded {key} ({len(data):,} bytes)")
                except Exception as exc:  # noqa: BLE001 - reported, and the CSV is not written
                    problems.append(f"{rp}: R2 refused {key}: {exc!r}")
                    continue
                got = fetch(url)
                if got is None:
                    problems.append(f"{rp}: could not read {url} back")
                    continue
                if sha256(got) != digest:
                    problems.append(f"{rp}: {url} serves bytes with SHA-256 {sha256(got)[:12]}..., "
                                    f"not the committed file's {digest[:12]}...")
                    continue
                log(f"{rp}: read {url} back; its SHA-256 matches")
        row = _new_row(inventory, old, rel, data, digest, key, usage,
                       report.sidecars.get(rel), etag, now_iso)
        if idx is None:
            rows.append(row)
            by_rp[rp] = len(rows) - 1
        else:
            rows[idx] = row

    # A file deleted from git keeps its row, and its R2 object stays. Nothing can link it any
    # more (a link to a missing file stopped this run above), so it is orphaned.
    current = {rules.repo_path(p) for p in report.images}
    for row in rows:
        rp = rules.normalize_ref(row.get("repo_path") or "")
        if row.get("source") == "launchbrightly" and rp and rp not in current:
            row.update({"source_type": "orphaned", "article_ids": "", "article_count": "0"})

    if problems:
        return _refuse(problems, f"{len(uploaded)} object(s) were uploaded and stay on R2 under "
                                 f"their content-hashed keys; the next run finds them")
    changed = [r for r in rows if r not in before]
    if not changed:
        log(f"NOTHING CHANGED: {len(report.images)} image(s) under {rules.ROOT}, all recorded. "
            f"{CSV_NAME} was not written.")
        return 0
    if dry_run:
        for line in planned:
            log(f"PLAN {line}")
        log(f"DRY RUN: {len(changed)} row(s) would be written; nothing was uploaded or written.")
        _print_rows(changed)
        return 0
    inventory.write_inventory(rows)
    log(f"WROTE {CSV_NAME}: {len(changed)} row(s) changed, {len(uploaded)} object(s) uploaded.")
    _print_rows(changed)
    return 0


def _print_rows(rows):
    shown = ("repo_path", "r2_key", "production_url", "source", "source_type", "article_ids",
             "content_sha256", "markdown_alt", "app_screen", "app_url", "location_source",
             "captured_at", "source_description", "source_ref", "needs_caption")
    for row in rows:
        log("  " + "; ".join(f"{c}={row.get(c, '')}" for c in shown))


def _refuse(problems, tail):
    log(f"REFUSED: {len(problems)} problem(s). {CSV_NAME} was not written; {tail}.")
    for problem in problems:
        log(f"  - {problem}")
        annotate("error", problem)
    return 1


def verify(repo, inventory, fetch, online):
    repo = Path(repo)
    report, usage, refs, problems = _check_inputs(repo)
    rows = inventory.read_inventory()
    by_rp = _rows_by_repo_path(rows, problems)
    linked = {r[0] for r in refs}
    checked = 0
    for rel in sorted(report.images):
        rp = rules.repo_path(rel)
        idx = by_rp.get(rp)
        if idx is None:
            if rp in linked:
                problems.append(f"{rp} is linked from an article but has no row in {CSV_NAME}")
            else:
                log(f"NOTICE: {rp} is not linked and has no row yet")
            continue
        row = rows[idx]
        digest = sha256(report.images[rel])
        key = rules.derive_key(rel, digest)
        if row.get("content_sha256") != digest:
            problems.append(f"{rp}: the row's content_sha256 {(row.get('content_sha256') or '')[:12]} "
                            f"is not the file's {digest[:12]}")
            continue
        if row.get("r2_key") != key or row.get("production_url") != rules.public_url(key):
            problems.append(f"{rp}: the row points at {row.get('production_url')!r}, not "
                            f"{rules.public_url(key)!r}")
            continue
        if online:
            got = fetch(row["production_url"])
            if got is None or sha256(got) != digest:
                problems.append(f"{rp}: {row['production_url']} does not serve the committed bytes")
                continue
        checked += 1
    if problems:
        log(f"VERIFY FAILED: {len(problems)} problem(s).")
        for problem in problems:
            log(f"  - {problem}")
            annotate("error", problem)
        return 1
    log(f"VERIFY OK: {checked} image(s) match their rows{' and their public bytes' if online else ''}; "
        f"{len(linked)} linked path(s), all present.")
    return 0


# ---------------------------------------------------------------------------------------
# self-test

_HUMAN = ("Amit", "amit@tallyfy.com")
_LB = (rules.LB_LOGIN, rules.LB_EMAIL)
PNG_A = b"\x89PNG\r\n\x1a\n" + b"image A" * 4
PNG_B = b"\x89PNG\r\n\x1a\n" + b"image B" * 4
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg" * 4


class _FakeR2:
    """Stands in for S3Uploader and the public URL. Records every call; makes no network call."""

    def __init__(self, objects=None, fail_put=False, serve=None):
        self.objects = dict(objects or {})
        self.fail_put = fail_put
        self.serve = dict(serve or {})
        self.calls = []

    def head(self, key):
        self.calls.append(("head", key))
        return {"etag": hashlib.md5(self.objects[key]).hexdigest()} if key in self.objects else None

    def put(self, key, body, content_type, cache_control):
        self.calls.append(("put", key, content_type, cache_control))
        if self.fail_put:
            raise RuntimeError("the fake R2 refused the upload")
        self.objects[key] = bytes(body)
        return {"etag": hashlib.md5(body).hexdigest()}

    def fetch(self, url):
        self.calls.append(("fetch", url))
        key = url[len(rules.PUBLIC_BASE) + 1:]
        return self.serve.get(key, self.objects.get(key))

    def names(self):
        return [c[0] for c in self.calls]


class _Scratch:
    """A scratch git repository with a docs folder, an inventory and a legacy row."""

    LEGACY = {"filename": "old.png", "r2_key": "tallyfy/pro/old.png",
              "production_url": "https://screenshots.tallyfy.com/tallyfy/pro/old.png",
              "source_type": "native", "file_type": ".png", "url_exists": "True",
              "ai_caption_alt": "Old screen", "needs_caption": "no", "source": "legacy-unknown"}

    def __init__(self, root, name):
        self.repo = Path(root) / name
        (self.repo / DOCS).mkdir(parents=True)
        self.git("init", "-q", "-b", "staging")
        with open(self.repo / CSV_NAME, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=AssetInventory.COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerow(dict({c: "" for c in AssetInventory.COLUMNS}, **self.LEGACY))
        self.commit("Start", files={f"{DOCS}/index.mdx": "---\ntitle: Home\n---\n\nNo images.\n"})

    @property
    def csv(self):
        return self.repo / CSV_NAME

    def git(self, *args, who=_HUMAN):
        env = dict(os.environ, GIT_AUTHOR_NAME=who[0], GIT_AUTHOR_EMAIL=who[1],
                   GIT_COMMITTER_NAME=who[0], GIT_COMMITTER_EMAIL=who[1])
        subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                       cwd=self.repo, env=env, check=True, capture_output=True)

    def commit(self, message, files=None, remove=(), who=_HUMAN):
        for rel, content in (files or {}).items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode() if isinstance(content, str) else content)
        for rel in remove:
            (self.repo / rel).unlink()
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message, who=who)

    def inventory(self):
        return AssetInventory(self.csv)

    def rows(self):
        return {r["repo_path"] or r["r2_key"]: r for r in self.inventory().read_inventory()}


def _article(title, body, art_id="b" * 32):
    return f"---\nid: {art_id}\ntitle: {title}\n---\n\n{body}\n"


def self_test():
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        log(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ""))

    def run(scratch, fake, **kwargs):
        built = []

        def make():
            built.append(1)
            return fake

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                rc = ingest(scratch.repo, scratch.inventory(), make, fake.fetch,
                            now=datetime(2026, 11, 6, tzinfo=timezone.utc), **kwargs)
            except CannotRun as exc:
                print(f"CANNOT RUN: {exc}")
                rc = 2
        return rc, buf.getvalue(), len(built)

    def run_verify(scratch, fake, online=True):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = verify(scratch.repo, scratch.inventory(), fake.fetch, online)
        return rc, buf.getvalue()

    root = rules.ROOT
    tasks = f"{root}tasks.png"
    tasks_key = rules.derive_key(tasks, sha256(PNG_A))
    page = _article("Track tasks", "Intro.\n\n## Your task list\n\nOpen it.\n\n"
                    "![Task list with due dates](/screenshots/launchbrightly/tasks.png)\n")

    with tempfile.TemporaryDirectory() as tmp:
        log("Self-test: ingest.")
        # 1. No screenshots/ folder at all: nothing to do, nothing written, no uploader built.
        # "Writes nothing" is checked by the file's inode as well as its bytes: write_inventory
        # always replaces the file, so a rewrite of identical bytes still shows.
        s = _Scratch(tmp, "empty")
        before, inode = s.csv.read_bytes(), s.csv.stat().st_ino
        fake = _FakeR2()
        rc, out, built = run(s, fake)
        check("GREEN no screenshots/ folder does nothing and writes nothing",
              rc == 0 and s.csv.read_bytes() == before and s.csv.stat().st_ino == inode
              and built == 0 and fake.calls == [], f"rc={rc} {out}")

        # 2. The same, but an article links an image that is not there.
        s.commit("Link a missing image", files={f"{DOCS}/a.mdx": page})
        before = s.csv.read_bytes()
        rc, out, built = run(s, fake)
        check("RED a link to a file that is not in the tree is refused, and the CSV is untouched",
              rc == 1 and "is not in the repository" in out and s.csv.read_bytes() == before
              and built == 0, f"rc={rc} {out}")

        # 3. A new image, linked from one article: uploaded once, read back, recorded.
        s.commit("Add the image", files={tasks: PNG_A})
        legacy_line = s.csv.read_text(encoding="utf-8").splitlines()[1]
        fake = _FakeR2()
        rc, out, built = run(s, fake)
        rows = s.rows()
        r = rows.get("/" + tasks, {})
        check("GREEN a new image is uploaded once under its content-hashed key",
              rc == 0 and [c for c in fake.calls if c[0] == "put"]
              == [("put", tasks_key, "image/png", CACHE_CONTROL)], f"rc={rc} {fake.calls} {out}")
        check("the upload is read back from its public URL", ("fetch", rules.public_url(tasks_key)) in fake.calls)
        check("the row records source, repo_path, hash, key, URL and file name",
              (r.get("source"), r.get("repo_path"), r.get("content_sha256"), r.get("r2_key"),
               r.get("production_url"), r.get("filename"))
              == ("launchbrightly", "/" + tasks, sha256(PNG_A), tasks_key, rules.public_url(tasks_key),
                  PurePosixPath(tasks_key).name), str(r))
        check("the row records where it is used and the page's alt text",
              (r.get("article_ids"), r.get("article_count"), r.get("source_type"), r.get("markdown_alt"))
              == ("b" * 32, "1", "native", "Task list with due dates"), str(r))
        check("with no sidecar the screen is inferred from the title and nearest heading",
              (r.get("app_screen"), r.get("location_source"), r.get("app_url"), r.get("captured_at"))
              == ("Track tasks, Your task list", "inferred", "", ""), str(r))
        check("a new image is queued for captions", r.get("needs_caption") == "yes"
              and all(r.get(c) == "" for c in CAPTION_COLUMNS), str(r))
        check("the legacy row is written back byte for byte",
              s.csv.read_text(encoding="utf-8").splitlines()[1] == legacy_line)

        # 4. Run again with nothing changed: no R2 call, no write.
        s.commit("Inventory repository screenshots", files={})
        before, inode = s.csv.read_bytes(), s.csv.stat().st_ino
        fake2 = _FakeR2(objects=fake.objects)
        rc, out, built = run(s, fake2)
        check("GREEN a rerun with nothing changed makes no R2 call and writes nothing",
              rc == 0 and s.csv.read_bytes() == before and s.csv.stat().st_ino == inode
              and built == 0 and fake2.calls == [], f"rc={rc} {fake2.calls} {out}")

        # 5. main: verify green, then red three ways.
        rc, out = run_verify(s, fake2)
        check("GREEN verify --online passes when rows and public bytes match", rc == 0, out)
        rc, out = run_verify(s, _FakeR2(serve={tasks_key: PNG_B}))
        check("RED verify --online fails when the public URL serves other bytes",
              rc == 1 and "does not serve the committed bytes" in out, out)
        rc, out = run_verify(s, _FakeR2(), online=False)
        check("GREEN verify without --online makes no fetch", rc == 0, out)
        good_csv = s.csv.read_bytes()
        s.csv.write_bytes(good_csv.replace(sha256(PNG_A).encode(), b"f" * 64))
        rc, out = run_verify(s, fake2, online=False)
        check("RED verify fails when the row's hash is not the file's", rc == 1 and "content_sha256" in out, out)
        s.csv.write_bytes(good_csv.replace(b"/" + tasks.encode(), b"/screenshots/launchbrightly/other.png"))
        rc, out = run_verify(s, fake2, online=False)
        check("RED verify fails when a linked image has no row", rc == 1 and "has no row" in out, out)
        s.csv.write_bytes(good_csv)

        # 6. The bytes change: a new key, the old object stays, captions and provenance cleared.
        rows = list(csv.DictReader(io.StringIO(good_csv.decode("utf-8"))))
        for row in rows:
            if row["repo_path"] == "/" + tasks:
                row.update({"ai_caption_alt": "A", "ai_caption_descriptive": "D", "ai_caption_seo": "S",
                            "needs_caption": "no", "captured_at": "2026-01-01", "source_description": "old",
                            "source_ref": "r1", "app_url": "/old", "app_screen": "Old screen",
                            "location_source": "launchbrightly"})
        s.inventory().write_inventory(rows)
        s.commit("Captions and provenance", files={})
        s.commit("Replace the image", files={tasks: PNG_B})
        fake3 = _FakeR2(objects=fake.objects)
        rc, out, built = run(s, fake3)
        r = s.rows().get("/" + tasks, {})
        new_key = rules.derive_key(tasks, sha256(PNG_B))
        check("GREEN changed bytes upload under a new key", rc == 0 and r.get("r2_key") == new_key
              and new_key != tasks_key and ("put", new_key, "image/png", CACHE_CONTROL) in fake3.calls,
              f"rc={rc} {out}")
        check("the old object is left on R2 (nothing deletes)", tasks_key in fake3.objects
              and not any(c[0] not in ("head", "put", "fetch") for c in fake3.calls), str(fake3.calls))
        check("changed bytes clear the three captions and set needs_caption=yes",
              all(r.get(c) == "" for c in CAPTION_COLUMNS) and r.get("needs_caption") == "yes", str(r))
        check("changed bytes clear captured_at, source_description, source_ref and app_url",
              all(r.get(c) == "" for c in PROVENANCE_CLEARED_ON_CHANGE), str(r))
        check("changed bytes with no sidecar infer the screen again",
              (r.get("app_screen"), r.get("location_source")) == ("Track tasks, Your task list", "inferred"), str(r))

        # 7. A good sidecar fills the provenance columns.
        sidecar = ('{"title": "Tasks", "screen": "Tasks, list view", "description": "The task list.",'
                   ' "app_url": "https://go.tallyfy.com/tasks?x=1", "captured_at": "2026-11-05T10:00:00Z",'
                   ' "recipe_id": "rec-9", "unknown": 1}')
        s.commit("Add a sidecar", files={f"{root}tasks.json": sidecar})
        rc, out, built = run(s, _FakeR2(objects=fake3.objects))
        r = s.rows().get("/" + tasks, {})
        check("GREEN a sidecar fills app_screen, app_url, captured_at, source_description and source_ref",
              rc == 0 and (r.get("app_screen"), r.get("app_url"), r.get("captured_at"),
                           r.get("source_description"), r.get("source_ref"), r.get("location_source"))
              == ("Tasks, list view", "/tasks", "2026-11-05T10:00:00Z", "The task list.", "rec-9",
                  "launchbrightly"), f"rc={rc} {r} {out}")
        check("an unknown sidecar key is reported, not stored", "ignored the unknown key 'unknown'" in out, out)
        check("a sidecar change with the same image makes no R2 call", built == 0, str(built))

        # 8. Red cases: each leaves the CSV and R2 untouched.
        def red(name, files, needle, remove=()):
            s2 = _Scratch(tmp, f"red-{len(results)}")
            s2.commit("Setup", files=files, remove=remove)
            before = s2.csv.read_bytes()
            f2 = _FakeR2()
            rc, out, built = run(s2, f2)
            check(f"RED {name}", rc == 1 and needle in out and s2.csv.read_bytes() == before
                  and not any(c[0] == "put" for c in f2.calls), f"rc={rc} {out}")

        red("a bad sidecar (another host) is refused",
            {tasks: PNG_A, f"{root}tasks.json": '{"app_url": "https://evil.example/x"}'}, "is not on tallyfy.com")
        red("a sidecar that is not JSON is refused", {tasks: PNG_A, f"{root}tasks.json": "{nope"},
            "is not valid UTF-8 JSON")
        red("a non-image file is refused", {f"{root}notes.txt": "hello"}, "is not an allowed image")
        red("an SVG is refused", {f"{root}logo.svg": "<svg/>"}, "is not an allowed image")
        red("a file outside screenshots/launchbrightly/ is refused", {"screenshots/other/a.png": PNG_A},
            "may hold files")
        red("an image over 3 MiB is refused",
            {tasks: PNG_A + b"\x00" * (rules.MAX_IMAGE_BYTES - len(PNG_A) + 1)}, "over the 3,145,728 byte limit")
        red("JPEG bytes named .png are refused", {tasks: JPEG}, "the name says png but the bytes are jpeg")
        red("an upper-case name is refused", {f"{root}Tasks.png": PNG_A}, "the name must be")
        red("a link to a missing image is refused even when another image is fine",
            {tasks: PNG_A, f"{DOCS}/b.mdx": _article("B", "![Gone](/screenshots/launchbrightly/gone.png)")},
            "links /screenshots/launchbrightly/gone.png, which is not in the repository")
        red("a link outside screenshots/launchbrightly/ is refused",
            {f"{DOCS}/b.mdx": _article("B", "![Other](/screenshots/other.png)")}, "is not in the repository")

        # 9. The upload or the read-back fails: exit 1, no CSV write.
        s4 = _Scratch(tmp, "readback")
        s4.commit("Add", files={tasks: PNG_A, f"{DOCS}/a.mdx": page})
        before = s4.csv.read_bytes()
        rc, out, built = run(s4, _FakeR2(serve={tasks_key: PNG_B}))
        check("RED a read-back whose hash differs fails and writes nothing",
              rc == 1 and "not the committed file's" in out and s4.csv.read_bytes() == before, out)
        rc, out, built = run(s4, _FakeR2(fail_put=True))
        check("RED a failed upload fails and writes nothing",
              rc == 1 and "R2 refused" in out and s4.csv.read_bytes() == before, out)
        present = _FakeR2(objects={tasks_key: PNG_A})
        rc, out, built = run(s4, present)
        check("GREEN an object already on R2 is not uploaded again, but is read back",
              rc == 0 and "put" not in present.names() and "fetch" in present.names()
              and s4.rows()["/" + tasks]["r2_key"] == tasks_key, f"{present.calls} {out}")

        # 10. Unused images, and a file deleted from git.
        s5 = _Scratch(tmp, "orphans")
        canary = f"{root}pipeline-canary.png"
        gone = "/screenshots/launchbrightly/gone.png"
        s5.commit("Add", files={canary: PNG_A, f"{root}gone.png": PNG_B,
                                f"{DOCS}/b.mdx": _article("B", f"![Gone soon]({gone})")})
        rc, out, built = run(s5, _FakeR2())
        r = s5.rows()
        check("GREEN an image no article links is recorded as orphaned with no screen",
              rc == 0 and (r["/" + canary]["source_type"], r["/" + canary]["article_ids"],
                           r["/" + canary]["article_count"], r["/" + canary]["app_screen"],
                           r["/" + canary]["location_source"])
              == ("orphaned", "", "0", "", "inferred"), str(r.get("/" + canary)))
        check("a linked image starts out native", r.get(gone, {}).get("source_type") == "native", str(r.get(gone)))
        s5.commit("Inventory", files={})
        s5.commit("Delete one image and its link", remove=[f"{root}gone.png", f"{DOCS}/b.mdx"])
        fake5 = _FakeR2()
        rc, out, built = run(s5, fake5)
        r = s5.rows()
        check("GREEN a file deleted from git keeps its row, marked orphaned and unused",
              rc == 0 and gone in r and (r[gone]["source_type"], r[gone]["article_ids"],
                                         r[gone]["article_count"]) == ("orphaned", "", "0")
              and fake5.calls == [], f"{r.get(gone)} {out}")

        # 11. A commit to the CSV by LaunchBrightly stops everything.
        s6 = _Scratch(tmp, "lb-csv")
        s6.commit("Add", files={tasks: PNG_A, f"{DOCS}/a.mdx": page})
        s6.csv.write_text(s6.csv.read_text(encoding="utf-8").replace("Old screen", "Changed"), encoding="utf-8")
        s6.commit("LaunchBrightly edits the inventory", who=_LB)
        s6.commit("A person commits on top", files={f"{DOCS}/c.mdx": _article("C", "Text.")})
        before = s6.csv.read_bytes()
        fake6 = _FakeR2()
        rc, out, built = run(s6, fake6)
        check("RED a CSV commit authored by LaunchBrightly is refused before anything uploads",
              rc == 1 and "REFUSED" in out and "launchbrightly[bot]" in out and built == 0
              and s6.csv.read_bytes() == before, out)

        # 12. A dry run makes no R2 call and writes nothing, and prints the rows it would write.
        s7 = _Scratch(tmp, "dry")
        s7.commit("Add", files={tasks: PNG_A, f"{DOCS}/a.mdx": page})
        before = s7.csv.read_bytes()
        rc, out, built = run(s7, _FakeR2(), dry_run=True)
        check("GREEN --dry-run builds no uploader, writes nothing and prints the planned row",
              rc == 0 and built == 0 and s7.csv.read_bytes() == before and f"r2_key={tasks_key}" in out, out)

        # 13. A shallow clone cannot say who touched the CSV: exit 2.
        shallow = Path(tmp) / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + str(s7.repo), str(shallow)],
                       check=True, capture_output=True)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                ingest(shallow, AssetInventory(shallow / CSV_NAME), _FakeR2, _FakeR2().fetch)
            shallow_rc = 0
        except CannotRun:
            shallow_rc = 2
        check("RED a shallow checkout cannot run (exit 2)", shallow_rc == 2)

        # 14. The command line: exit codes, and no uploader for a no-op or a refusal.
        def cli(argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                return main(argv), buf.getvalue()

        rc, out = cli(["ingest", "--repo", str(s5.repo)])
        check("GREEN the command line exits 0 on a no-op", rc == 0 and "NOTHING CHANGED" in out, out)
        rc, out = cli(["ingest", "--repo", str(s6.repo)])
        check("RED the command line exits 1 on a refusal", rc == 1, out)
        rc, out = cli(["verify", "--repo", str(s4.repo)])
        check("GREEN the command line verify exits 0", rc == 0, out)
        rc, out = cli(["ingest", "--repo", str(Path(tmp) / "missing")])
        check("RED the command line exits 2 when it cannot run", rc == 2, out)

    log("Self-test: the S3 uploader, with a fake boto3 client.")

    class _Err(Exception):
        def __init__(self, status, code):
            super().__init__(code)
            self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}

    class _Client:
        def __init__(self, fail=None):
            self.fail, self.calls = fail, []

        def head_object(self, **kw):
            self.calls.append(("head_object", kw))
            if self.fail:
                raise self.fail
            return {"ETag": '"abc"', "ContentLength": 3}

        def put_object(self, **kw):
            self.calls.append(("put_object", kw))
            return {"ETag": '"def"'}

    up = S3Uploader(_Client())
    check("head returns the etag of an object that exists", up.head("k") == {"etag": "abc", "size": 3})
    check("head returns None on a 404", S3Uploader(_Client(_Err(404, "404"))).head("k") is None)
    raised = False
    try:
        S3Uploader(_Client(_Err(403, "AccessDenied"))).head("k")
    except _Err:
        raised = True
    check("RED head raises on a 403, which must fail the job", raised)
    client = _Client()
    S3Uploader(client).put("launchbrightly/a.0123456789ab.png", b"x", "image/png", CACHE_CONTROL)
    check("put sends the bucket, key, body, content type and Cache-Control",
          client.calls == [("put_object", {"Bucket": "screenshots", "Key": "launchbrightly/a.0123456789ab.png",
                                           "Body": b"x", "ContentType": "image/png",
                                           "CacheControl": CACHE_CONTROL})], str(client.calls))
    check("the uploader has no way to delete", not any("delete" in n for n in dir(S3Uploader)))
    try:
        S3Uploader.from_env({"R2_ACCESS_KEY_ID": "x"})
        named = ""
    except CannotRun as exc:
        named = str(exc)
    check("RED from_env names every missing secret", "R2_SECRET_ACCESS_KEY" in named
          and "CLOUDFLARE_ACCOUNT_ID" in named and "R2_ACCESS_KEY_ID," not in named, named)
    try:
        S3Uploader.from_env({"R2_ACCESS_KEY_ID": "x", "R2_SECRET_ACCESS_KEY": "y",
                             "CLOUDFLARE_ACCOUNT_ID": "not-an-account"})
        named = ""
    except CannotRun as exc:
        named = str(exc)
    check("RED from_env refuses an account id that is not 32 hex characters", "32 lower-case hex" in named, named)

    passed = sum(results)
    log(f"SELF-TEST {'PASSED' if passed == len(results) else 'FAILED'}: {passed} of {len(results)} case(s)")
    return 0 if passed == len(results) else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd")
    ip = sub.add_parser("ingest", help="upload and record (staging)")
    ip.add_argument("--dry-run", action="store_true", help="no network call, no write; print the plan")
    ip.add_argument("--repo", default=str(REPO_ROOT))
    vp = sub.add_parser("verify", help="check rows against the files (main)")
    vp.add_argument("--online", action="store_true", help="also download each image and compare")
    vp.add_argument("--repo", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_usage()
        return 2
    try:
        repo = Path(args.repo).resolve()
        if not (repo / CSV_NAME).is_file():
            raise CannotRun(f"no {CSV_NAME} in {repo}")
        inventory = AssetInventory(repo / CSV_NAME)
        if args.cmd == "ingest":
            return ingest(repo, inventory, S3Uploader.from_env, http_fetch, dry_run=args.dry_run)
        return verify(repo, inventory, http_fetch, args.online)
    except CannotRun as exc:
        log(f"CANNOT RUN: {exc}")
        annotate("error", f"repo_screenshots.py could not run: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash must be 2, never a pass
        import traceback
        traceback.print_exc()
        log(f"CRASHED: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
