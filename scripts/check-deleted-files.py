#!/usr/bin/env python3
"""
check-deleted-files.py - remove from the Answers index every entry whose page is gone.

    python scripts/check-deleted-files.py --dir=$PWD --collection_name=tyfy \\
        --answers_api_key=KEY --base_url=https://staging.answers.tallyfy.com
    python scripts/check-deleted-files.py ... --dry-run          report only, delete nothing
    python scripts/check-deleted-files.py --self-test [--target PATH]

WHOLE TREE, EVERY RUN (owner decision 218, 2026-10-03, tallyfy/documentation#296 criterion 2).
Until then this script read one commit's deleted files from the GitHub API, so a page deleted in
a push whose run was dropped from the concurrency queue, or whose id changed, stayed in search
for good. Measured read only on 2026-10-03: the staging index held 596 entries for 593 pages,
three of them for no page at all (pro/integrations/analytics/snowflake, denizen/temp, and an id
the due-date page carried for a day in September), and the production index held one
(snowflake). This version lists the collection, compares every entry's uid with the ids of every
page in the checked out tree, and deletes the entries that no page carries. It keeps no state.

WHICH IDS COUNT AS A PAGE. Every `.mdx` under src/content/docs that has an id, including
pro/changelog/** and 404.mdx, which are never uploaded: an entry is deleted only when no file in
the tree carries its uid. Both sides are compared as 32 lowercase hex digits, so an entry stored
with hyphens or capitals still matches its page.

CAPS, so a first run or a bug cannot flood the Answers API:
  --max-deletes   at most this many deletes per run (default 25); the rest wait for the next run,
                  which the run says.
  --max-fraction  if the entries to delete are more than this share of the index (default 0.2),
                  delete nothing and fail. A wrong --dir or a broken id read would make every
                  entry look orphaned; that must stop the run, not empty the index.
  --min-pages     fewer page ids than this (default 100) means the tree is not the docs tree.

Every delete is read back: the collection is listed again and each deleted uid must be gone.
The Answers API answers 200 to a delete whether or not anything matched, so the status code
alone proves nothing.

The key goes in the Authorization header as it is, not as `Bearer <key>` (measured 2026-08-09,
tallyfy/documentation#124; the stored secret already starts with `Bearer `).

EXIT CODES
  0  done: nothing to delete, or every delete this run read back as gone
  1  refused (too many orphans), a delete did not land, or a self-test case failed
  2  could not run: the index or the tree could not be read, or a bad argument. Nothing deleted.
"""

import argparse
import os
import sys
import uuid

import frontmatter
import requests

def log(msg=""):
    # print, not logging: a `::error::` annotation only works at the start of a line.
    print(msg, flush=True)

DOCS = os.path.join("src", "content", "docs")
DEFAULT_ANSWERS_BASE_URL = "https://answers.tallyfy.com"
DEFAULT_MAX_DELETES = 25
DEFAULT_MAX_FRACTION = 0.2
DEFAULT_MIN_PAGES = 100


class CannotRun(Exception):
    """Exit 2. Nothing has been deleted when this is raised."""


def norm(uid):
    """A uid as 32 lowercase hex digits, or the stripped lowercase text when it is not a UUID."""
    text = str(uid).strip()
    try:
        return uuid.UUID(text).hex
    except (ValueError, AttributeError, TypeError):
        return text.lower()


def tree_ids(root, min_pages):
    """The normalized id of every page in the tree. Raises CannotRun."""
    base = os.path.join(root, DOCS)
    if not os.path.isdir(base):
        raise CannotRun(f"no {DOCS} under {root}")
    ids, unreadable = set(), []
    for folder, _, files in os.walk(base):
        for name in files:
            if not name.endswith(".mdx"):
                continue
            full = os.path.join(folder, name)
            try:
                value = frontmatter.load(full).get("id")
            except Exception as exc:  # noqa: BLE001 - any parse failure stops the run
                unreadable.append(f"{os.path.relpath(full, root)}: {exc}")
                continue
            if value is not None and str(value).strip():
                ids.add(norm(value))
    if unreadable:
        raise CannotRun("front matter could not be read, so which pages exist is unknown:\n  "
                        + "\n  ".join(unreadable))
    if len(ids) < min_pages:
        raise CannotRun(f"only {len(ids)} page id(s) under {base}, fewer than {min_pages}; "
                        f"this is not the docs tree")
    return ids


def list_index(objects_url, key):
    """[(raw uid, url, title)] for every entry. Raises CannotRun.

    The route answers HTTP 200 with {"error": "Collection not found", "status": 404} for a
    collection that does not exist, so the body's own status and a `message` list are both
    required before anything counts as a listing."""
    try:
        r = requests.get(objects_url, headers={"Authorization": key}, timeout=300)
    except requests.RequestException as exc:
        raise CannotRun(f"listing {objects_url} failed: {exc}")
    if r.status_code != 200:
        raise CannotRun(f"listing {objects_url} answered HTTP {r.status_code}")
    try:
        body = r.json()
    except ValueError:
        raise CannotRun(f"listing {objects_url} did not answer JSON")
    if not isinstance(body, dict) or body.get("status") != 200 or not isinstance(body.get("message"), list):
        shown = {k: v for k, v in body.items() if k != "message"} if isinstance(body, dict) else body
        raise CannotRun(f"listing {objects_url} did not return a collection: {str(shown)[:200]}")
    out = []
    for obj in body["message"]:
        if not isinstance(obj, dict) or obj.get("uid") in (None, ""):
            raise CannotRun(f"an index entry has no uid: {str(obj)[:200]}")
        out.append((str(obj["uid"]), obj.get("url"), obj.get("title")))
    return out


def reconcile(root, base_url, collection, key, max_deletes, max_fraction, min_pages, dry_run):
    objects_url = f"{base_url.rstrip('/')}/collections/{collection}/objects"
    ids = tree_ids(root, min_pages)
    index = list_index(objects_url, key)
    orphans = sorted((e for e in index if norm(e[0]) not in ids), key=lambda e: (str(e[1]), e[0]))
    log(f"Answers index {objects_url}: {len(index)} entries. Tree: {len(ids)} page ids. "
        f"Entries no page carries: {len(orphans)}.")
    for uid, url, title in orphans[:50]:
        log(f"  orphan {uid}  {url}  {title!r}")
    if not orphans:
        log("Nothing to delete.")
        return 0
    if len(orphans) > max_fraction * len(index):
        log(f"::error::REFUSED: {len(orphans)} of {len(index)} index entries match no page, more "
            f"than {max_fraction:.0%}. Nothing was deleted. A wrong tree or a broken id read makes "
            f"every entry look orphaned, so a person has to look. To prune on purpose, run this "
            f"script by hand with a higher --max-fraction.")
        log("REFUSED")
        return 1
    batch, later = orphans[:max_deletes], orphans[max_deletes:]
    if dry_run:
        log(f"DRY RUN: would delete {len(batch)} this run (cap {max_deletes}), {len(later)} later.")
        return 0
    failed = []
    for uid, url, _ in batch:
        try:
            r = requests.delete(f"{objects_url}/{uid}", headers={"Authorization": key}, timeout=60)
            if r.status_code == 200:
                log(f"  deleted {uid}  {url}")
            else:
                failed.append((uid, f"HTTP {r.status_code}"))
        except requests.RequestException as exc:
            failed.append((uid, f"{type(exc).__name__}: {exc}"))
    # Read back. A 200 from the delete route says nothing about whether an entry matched.
    try:
        left = {norm(e[0]) for e in list_index(objects_url, key)}
    except CannotRun as exc:
        log(f"::error::the deletes were sent but could not be read back: {exc}")
        return 1
    for uid, _, _ in batch:
        if norm(uid) in left and not any(uid == f[0] for f in failed):
            failed.append((uid, "still listed after the delete"))
    if failed:
        log(f"::error::{len(failed)} delete(s) did not land:")
        for uid, why in failed:
            log(f"  {uid}: {why}")
        return 1
    log(f"Deleted {len(batch)} entr{'y' if len(batch) == 1 else 'ies'}, each read back as gone.")
    if later:
        log(f"::warning::{len(later)} more orphaned entr{'y waits' if len(later) == 1 else 'ies wait'} "
            f"for the next run (cap {max_deletes} per run).")
    return 0


# ---------------------------------------------------------------------------------------
# self-test: drives the CLI of --target (default this file) against a fake Answers API on
# 127.0.0.1, so the real HTTP calls run, and the same cases can be pointed at an older copy.

def _self_test(target):
    import json
    import subprocess
    import tempfile
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    key = "Bearer self-test-key"
    state = {"objects": [], "deletes": [], "ignore": set(), "list_status": 200, "list_body": None}

    class Fake(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, payload):
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get("Authorization") != key:
                return self._send(403, {"error": "Forbidden"})
            if self.path != "/collections/tyfy/objects":
                return self._send(200, {"error": "Collection not found", "status": 404})
            if state["list_body"] is not None:
                return self._send(state["list_status"], state["list_body"])
            return self._send(state["list_status"], {"message": list(state["objects"]), "status": 200})

        def do_DELETE(self):
            if self.headers.get("Authorization") != key:
                return self._send(403, {"error": "Forbidden"})
            uid = self.path.rsplit("/", 1)[-1]
            state["deletes"].append(uid)
            if uid not in state["ignore"]:
                state["objects"] = [o for o in state["objects"] if o["uid"] != uid]
            return self._send(200, {"message": "Object is deleted successfully"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    cases = []

    def case(name, ok, detail=""):
        cases.append(ok)
        print(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}", flush=True)

    def hexid(i):
        # md5 hex, like a real id. An all-digit id such as 000...001 is read by YAML as an
        # integer, which no real page carries.
        import hashlib
        return hashlib.md5(f"self-test {i}".encode()).hexdigest()

    def tree(root, n, extra=()):
        for i in range(n):
            path = os.path.join(root, DOCS, "pro", f"p{i}.mdx")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"---\nid: {hexid(i + 1)}\ntitle: P{i}\n---\n\nBody {i}.\n")
        for rel, text in extra:
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

    def index(uids):
        state["objects"] = [{"uid": u, "url": f"/x/{u}/", "title": "T"} for u in uids]
        state["deletes"], state["ignore"] = [], set()
        state["list_status"], state["list_body"] = 200, None

    def run(root, *extra, k=key):
        r = subprocess.run([sys.executable, target, f"--dir={root}", "--collection_name=tyfy",
                            f"--answers_api_key={k}", f"--base_url={base}", *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def left():
        return {o["uid"] for o in state["objects"]}

    print(f"Self-test of {target}: whole-tree Answers prune against a fake API at {base}.", flush=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "repo")
            changelog_id = hexid(9001)
            tree(d, 120, extra=[
                ("src/content/docs/pro/changelog/2026/c.mdx", f"---\nid: {changelog_id}\ntitle: C\n---\n\nC.\n"),
                ("src/content/docs/pro/no-id.mdx", "---\ntitle: N\n---\n\nNo id.\n"),
            ])
            pages = [hexid(i + 1) for i in range(120)]
            gone = [hexid(5001), hexid(5002)]
            shaped = str(uuid.UUID(hexid(7))).upper()     # page p6's id, stored with hyphens, upper case
            index(pages[:6] + [shaped] + pages[7:] + [changelog_id] + gone)

            rc, out = run(d)
            case("deletes the entries whose page is gone, and only those",
                 rc == 0 and sorted(state["deletes"]) == sorted(gone) and not (set(gone) & left()),
                 f"rc={rc} deleted={state['deletes']}")
            case("an entry stored with hyphens and capitals still matches its page and is kept",
                 shaped in left())
            case("an entry for a page search never indexes (pro/changelog) that still carries the "
                 "id is kept", changelog_id in left())
            before = list(state["objects"])
            state["deletes"] = []
            rc, out = run(d)
            case("a second run deletes nothing (idempotent)",
                 rc == 0 and state["deletes"] == [] and state["objects"] == before
                 and "Nothing to delete." in out, f"rc={rc} deleted={state['deletes']}")

            orphans = [hexid(6000 + i) for i in range(5)]
            index(pages + orphans)
            rc, out = run(d, "--max-deletes=3")
            case("the cap deletes --max-deletes entries and says how many wait",
                 rc == 0 and len(state["deletes"]) == 3 and "2 more orphaned entries wait" in out,
                 f"rc={rc} deleted={len(state['deletes'])}")
            rc, out = run(d, "--max-deletes=3")
            case("and the next run deletes the rest", rc == 0 and not (set(orphans) & left()),
                 f"rc={rc}")

            index(pages + orphans)
            rc, out = run(d, "--dry-run")
            case("--dry-run reports and deletes nothing",
                 rc == 0 and state["deletes"] == [] and "would delete 5" in out, f"rc={rc}")

            index(pages[:90] + [hexid(8000 + i) for i in range(30)])
            rc, out = run(d)
            case("more orphans than --max-fraction of the index: refused, nothing deleted, exit 1",
                 rc == 1 and state["deletes"] == [] and "REFUSED" in out, f"rc={rc}")

            index(pages + gone)
            state["ignore"] = {gone[0]}
            rc, out = run(d)
            case("a delete that answers 200 but leaves the entry is caught by the read back",
                 rc == 1 and "still listed after the delete" in out, f"rc={rc}")

            index(pages + gone)
            state["list_body"] = {"error": "Collection not found", "status": 404}
            rc, out = run(d)
            case("an index that answers 200 with an error body is exit 2, never 'nothing to delete'",
                 rc == 2 and state["deletes"] == [] and "did not return a collection" in out, f"rc={rc}")

            index(pages + gone)
            rc, out = run(d, k="Bearer wrong-key")
            case("a rejected key (403) is exit 2 and deletes nothing",
                 rc == 2 and state["deletes"] == [] and "HTTP 403" in out, f"rc={rc}")

            index(pages + gone)
            small = os.path.join(tmp, "small")
            tree(small, 5)
            rc, out = run(small)
            case("a tree with too few ids (a wrong --dir) is exit 2 and deletes nothing",
                 rc == 2 and state["deletes"] == [] and "this is not the docs tree" in out, f"rc={rc}")

            index(pages + gone)
            with open(os.path.join(d, DOCS, "pro", "broken.mdx"), "w", encoding="utf-8") as fh:
                fh.write("---\ntitle: [unclosed\n---\n\nBroken.\n")
            rc, out = run(d)
            case("a page whose front matter cannot be read stops the run before any delete",
                 rc == 2 and state["deletes"] == [] and "could not be read" in out, f"rc={rc}")
    finally:
        server.shutdown()

    failed = cases.count(False)
    if failed:
        print(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).", flush=True)
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).", flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove Answers index entries whose page is gone.")
    parser.add_argument("--dir", help="repository root (the folder holding src/content/docs)")
    parser.add_argument("--collection_name")
    parser.add_argument("--answers_api_key")
    parser.add_argument("--base_url", default=DEFAULT_ANSWERS_BASE_URL)
    parser.add_argument("--max-deletes", type=int, default=DEFAULT_MAX_DELETES)
    parser.add_argument("--max-fraction", type=float, default=DEFAULT_MAX_FRACTION)
    parser.add_argument("--min-pages", type=int, default=DEFAULT_MIN_PAGES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--target", default=os.path.abspath(__file__),
                        help="with --self-test: the copy of this script to test")
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test(os.path.abspath(args.target))
    if not (args.dir and args.collection_name and args.answers_api_key) or args.max_deletes < 1 \
            or not 0 < args.max_fraction <= 1 or args.min_pages < 1:
        print("CANNOT RUN: pass --dir, --collection_name and --answers_api_key, with "
              "--max-deletes of 1 or more and --max-fraction above 0 and at most 1", flush=True)
        return 2
    try:
        return reconcile(os.path.abspath(args.dir), args.base_url, args.collection_name,
                         args.answers_api_key, args.max_deletes, args.max_fraction, args.min_pages,
                         args.dry_run)
    except CannotRun as exc:
        print(f"::error::check-deleted-files could not run, so nothing was deleted: {exc}", flush=True)
        print(f"CANNOT RUN: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
