#!/usr/bin/env python3
"""
The rules for screenshots committed to this repository (tallyfy/documentation#464).

LaunchBrightly opens pull requests that add images under screenshots/launchbrightly/ and link
them from articles by repository path, such as ![Task list](/screenshots/launchbrightly/tasks.png).
Two scripts apply the same rules, so they live here once:

  scripts/asset_management/repo_screenshots.py  uploads the images on staging, records them in
                                                documentation_assets.csv, and checks them on main
  scripts/lb-pr-guard.py                        checks a pull request before it merges

The rules:
  - Files live under screenshots/launchbrightly/ and nowhere else under screenshots/.
  - An image is PNG, JPEG, GIF or WebP, judged by its first bytes, and its extension must say
    the same type. SVG is refused. At most 3 MiB.
  - A name, relative to that folder, matches NAME_RE: lower case letters, digits and hyphens,
    in folders of the same.
  - An image may have a sidecar, <same name>.json, of at most 8 KB, describing it. The keys are
    title, screen, description, app_url, captured_at and recipe_id. Other keys are ignored with
    a notice. app_url is stored as a path: query and fragment are dropped, and a full URL is
    accepted only on tallyfy.com or one of its subdomains.
  - An image uploads to the key derive_key() gives, which carries the first 12 hex characters
    of its SHA-256, so a changed image gets a new URL and the old one keeps working.

Standard library only, because the pull request guard installs nothing.

  python3 scripts/asset_management/repo_screenshot_rules.py --self-test
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit

REPO_FOLDER = "screenshots/"
ROOT = "screenshots/launchbrightly/"
PUBLIC_BASE = "https://screenshots.tallyfy.com"
KEY_PREFIX = "launchbrightly/"

MAX_IMAGE_BYTES = 3 * 1024 * 1024        # 3,145,728
MAX_SIDECAR_BYTES = 8 * 1024             # 8,192

IMAGE_EXTS = ("png", "jpg", "jpeg", "gif", "webp")
# Which type each extension promises, as sniff_image_type() names types.
EXT_TYPE = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "gif": "gif", "webp": "webp"}
CONTENT_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)*\.(png|jpe?g|gif|webp)$")
SIDECAR_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)*\.json$")

SIDECAR_KEYS = ("title", "screen", "description", "app_url", "captured_at", "recipe_id")

# Git file modes of a regular file. A symlink (120000) or a submodule (160000) under
# screenshots/ is refused: a link can point outside the folder, and a submodule has no bytes.
REGULAR_MODES = ("100644", "100755")

# The LaunchBrightly GitHub App's bot account.
LB_LOGIN = "launchbrightly[bot]"
LB_ID = "270903805"
LB_EMAIL = "270903805+launchbrightly[bot]@users.noreply.github.com"

# An image an article links by repository path: ![alt](/screenshots/...) or src="/screenshots/...".
# The lookbehind keeps it to a path that starts a link target or an attribute value, so it never
# matches inside a URL such as https://tallyfy.com/products/screenshots/. The same pattern as
# audit_sync.py's _REPO_PATH_RE.
REF_RE = re.compile(r"(?<=[(<\"'])/screenshots/[^\s\"'<>)\]\\]+")
_MD_IMAGE_RE = re.compile(r"!\[([^\]\n]*)\]\(\s*<?([^\s)>]+)>?")
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SRC_RE = re.compile(r"\bsrc\s*=\s*([\"'])(.*?)\1", re.IGNORECASE)
_ALT_RE = re.compile(r"\balt\s*=\s*([\"'])(.*?)\1", re.IGNORECASE)
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# One image on a line of its own, which is all a LaunchBrightly pull request may add to an
# article. An optional list marker, alt text of 1 to 250 characters with none of [ ] { } < > \
# (MDX could read braces or angle brackets as code), a repository path under
# screenshots/launchbrightly/ or a screenshots.tallyfy.com URL with no spaces or parentheses
# (so a second link cannot ride on the same line), and an optional quoted title.
IMAGE_LINE_RE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+\.\s+)?"
    r"!\[(?P<alt>[^\[\]\n{}<>\\]{1,250})\]"
    r"\((?P<url>/screenshots/launchbrightly/[^\s()]+|https://screenshots\.tallyfy\.com/[^\s()]+)"
    r"(?:\s+\"[^\"\n{}<>]*\")?\)\s*$"
)
# A line a LaunchBrightly pull request may remove: blank, or one that holds an image.
REMOVABLE_LINE_RE = re.compile(r"^\s*$|!\[|<img\b", re.IGNORECASE)

_ISO_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)


def sniff_image_type(data):
    """The image type the first bytes declare, or None: 'png', 'jpeg', 'gif' or 'webp'."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def extension(path):
    """The lower-case extension of a path, without the dot."""
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def stem(path):
    """The path without its extension."""
    return path[: -(len(extension(path)) + 1)] if extension(path) else path


def content_type(path):
    return CONTENT_TYPES[EXT_TYPE[extension(path)]]


def derive_key(rel_path, sha256):
    """screenshots/launchbrightly/a/b.png -> launchbrightly/a/b.<first 12 of sha256>.png"""
    if not rel_path.startswith(ROOT):
        raise ValueError(f"{rel_path} is not under {ROOT}")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
        raise ValueError(f"{sha256!r} is not a SHA-256 in lower-case hex")
    inner = rel_path[len(ROOT):]
    return f"{KEY_PREFIX}{stem(inner)}.{sha256[:12]}.{extension(inner)}"


def public_url(key):
    return f"{PUBLIC_BASE}/{key}"


def repo_path(rel_path):
    """The root-relative path an article links: screenshots/x.png -> /screenshots/x.png"""
    return "/" + rel_path.lstrip("/")


def normalize_ref(raw):
    """A reference as found in an article, decoded, with trailing punctuation and slash dropped."""
    p = unquote(raw.strip()).rstrip(".,;").rstrip("/")
    return "/" + p.lstrip("/") if p else ""


def image_problems(rel_path, data, mode="100644"):
    """Why this file cannot be a repository screenshot, as a list. Empty means it can."""
    problems = []
    if not rel_path.startswith(ROOT):
        return [f"{rel_path}: only {ROOT} may hold files under {REPO_FOLDER}"]
    if mode not in REGULAR_MODES:
        return [f"{rel_path}: is not a regular file (git mode {mode}); links and submodules are refused"]
    inner = rel_path[len(ROOT):]
    if not NAME_RE.match(inner):
        problems.append(f"{rel_path}: the name must be lower case letters, digits and hyphens, in "
                        f"folders of the same, ending .png, .jpg, .jpeg, .gif or .webp")
    if len(data) == 0:
        problems.append(f"{rel_path}: is empty")
    elif len(data) > MAX_IMAGE_BYTES:
        problems.append(f"{rel_path}: is {len(data):,} bytes, over the {MAX_IMAGE_BYTES:,} byte limit")
    found = sniff_image_type(data)
    promised = EXT_TYPE.get(extension(rel_path))
    if found is None:
        problems.append(f"{rel_path}: its bytes are not a PNG, JPEG, GIF or WebP image")
    elif promised is not None and found != promised:
        problems.append(f"{rel_path}: the name says {promised} but the bytes are {found}")
    return problems


def _valid_iso(value):
    m = _ISO_RE.match(value)
    if not m:
        return False
    year, month, day, hour, minute, second, _fraction, offset = m.groups()
    try:
        datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
        if offset and offset not in ("Z",):
            sign = 1 if offset[0] == "+" else -1
            hh, mm = int(offset[1:3]), int(offset[-2:])
            if hh > 23 or mm > 59:
                return False
            timezone(sign * timedelta(hours=hh, minutes=mm))
    except ValueError:
        return False
    return True


def clean_app_url(value):
    """(path, problem). A path keeps only its path; a full URL must be https on tallyfy.com or a
    subdomain of it, and also keeps only its path. Anything else is a problem."""
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        return "", f"app_url {value!r} does not parse: {exc}"
    if parts.scheme or parts.netloc:
        host = (parts.hostname or "").lower()
        if parts.scheme.lower() != "https" or not (host == "tallyfy.com" or host.endswith(".tallyfy.com")):
            return "", (f"app_url {value!r} is not on tallyfy.com; give the app screen's path, "
                        f"such as /tasks")
    path = parts.path or "/"
    if not path.startswith("/"):
        return "", f"app_url {value!r} must be a path starting with /"
    return path, None


def parse_sidecar(rel_path, data):
    """(fields, problems, notices) for a sidecar's bytes. fields holds only the known keys that
    have a usable value, each as a single-line string; app_url is reduced to its path."""
    fields, problems, notices = {}, [], []
    if len(data) > MAX_SIDECAR_BYTES:
        return fields, [f"{rel_path}: is {len(data):,} bytes, over the {MAX_SIDECAR_BYTES:,} byte "
                        f"limit for a sidecar"], notices
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return fields, [f"{rel_path}: is not valid UTF-8 JSON ({exc})"], notices
    if not isinstance(doc, dict):
        return fields, [f"{rel_path}: must be a JSON object"], notices
    for key in sorted(doc):
        if key not in SIDECAR_KEYS:
            notices.append(f"{rel_path}: ignored the unknown key {key!r}")
    for key in SIDECAR_KEYS:
        value = doc.get(key)
        if value is None:
            continue
        if key == "recipe_id" and isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            problems.append(f"{rel_path}: {key} must be a string")
            continue
        value = " ".join(value.split())
        if not value:
            continue
        if key == "app_url":
            value, problem = clean_app_url(value)
            if problem:
                problems.append(f"{rel_path}: {problem}")
                continue
        if key == "captured_at" and not _valid_iso(value):
            problems.append(f"{rel_path}: captured_at {value!r} is not an ISO 8601 date or time")
            continue
        fields[key] = value
    return fields, problems, notices


class TreeReport:
    def __init__(self):
        self.images = {}      # rel_path -> bytes
        self.sidecars = {}    # image rel_path -> fields
        self.problems = []
        self.notices = []


def check_tree(files, all_paths=None):
    """Judge files under screenshots/.

    files      {rel_path: (mode, read)} for the files to judge; read() returns the bytes.
    all_paths  every path under screenshots/ in the tree, used to pair a sidecar with its image.
               Defaults to the keys of files.

    Every file must be an allowed image or the sidecar of exactly one image in the tree.
    """
    report = TreeReport()
    all_paths = set(files) if all_paths is None else set(all_paths)
    image_paths = {p for p in all_paths if p.startswith(ROOT) and extension(p) in IMAGE_EXTS}
    by_stem = {}
    for p in image_paths:
        by_stem.setdefault(stem(p), []).append(p)
    for rel in sorted(files):
        mode, read = files[rel]
        ext = extension(rel)
        if not rel.startswith(ROOT):
            report.problems.append(f"{rel}: only {ROOT} may hold files under {REPO_FOLDER}")
            continue
        if mode not in REGULAR_MODES:
            report.problems.append(f"{rel}: is not a regular file (git mode {mode}); links and "
                                   f"submodules are refused")
            continue
        if ext in IMAGE_EXTS:
            data = read()
            problems = image_problems(rel, data, mode)
            report.problems += problems
            if not problems:
                report.images[rel] = data
        elif ext == "json":
            if not SIDECAR_NAME_RE.match(rel[len(ROOT):]):
                report.problems.append(f"{rel}: a sidecar's name must be lower case letters, digits "
                                       f"and hyphens, ending .json")
                continue
            owners = sorted(by_stem.get(stem(rel), []))
            if len(owners) != 1:
                report.problems.append(
                    f"{rel}: a sidecar must sit beside exactly one image of the same name; found "
                    f"{len(owners)}" + (f" ({', '.join(owners)})" if owners else ""))
                continue
            data = read()
            fields, problems, notices = parse_sidecar(rel, data)
            report.problems += problems
            report.notices += notices
            if not problems:
                report.sidecars[owners[0]] = fields
        else:
            report.problems.append(f"{rel}: is not an allowed image (png, jpg, jpeg, gif, webp) "
                                   f"or a .json sidecar")
    return report


def lines_outside_fences(text):
    """(line number, line) for every line of text that is not inside a fenced code block."""
    fence = None
    for number, line in enumerate(text.splitlines(), start=1):
        m = _FENCE_RE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                continue
            yield number, line
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                and not line.strip()[len(m.group(1)):].strip():
            fence = None


def refs_in_line(line):
    """[(normalized path, alt text or None)] for each /screenshots/ reference on one line."""
    alts = {}
    for m in _MD_IMAGE_RE.finditer(line):
        alts.setdefault(normalize_ref(m.group(2)), m.group(1).strip())
    for tag in _IMG_TAG_RE.finditer(line):
        src, alt = _SRC_RE.search(tag.group(0)), _ALT_RE.search(tag.group(0))
        if src:
            alts.setdefault(normalize_ref(src.group(2)), alt.group(2).strip() if alt else "")
    out = []
    for m in REF_RE.finditer(line):
        path = normalize_ref(m.group(0))
        out.append((path, alts.get(path)))
    return out


def find_references(text):
    """[(normalized path, line number, alt text or None)] outside fenced code blocks."""
    return [(path, number, alt)
            for number, line in lines_outside_fences(text)
            for path, alt in refs_in_line(line)]


def alt_problem(alt):
    """Why alt text is not acceptable on a LaunchBrightly image, or None."""
    if not (alt or "").strip():
        return "the alt text is empty"
    if "launchbrightly" in alt.lower():
        return "the alt text names LaunchBrightly; describe what the image shows"
    return None


# ---------------------------------------------------------------------------------------
# self-test

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF = b"GIF89a" + b"\x00" * 16
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 8
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'


def self_test():
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ""))

    def tree(entries, all_paths=None):
        return check_tree({p: (m, (lambda d=d: d)) for p, (m, d) in entries.items()}, all_paths)

    def refused(entries, needle, all_paths=None):
        r = tree(entries, all_paths)
        return any(needle in p for p in r.problems), r.problems

    root = ROOT
    print("Self-test: images (type by bytes, size, name, folder, file mode).")
    for name, data in (("a.png", PNG), ("b.jpg", JPEG), ("c.jpeg", JPEG), ("d.gif", GIF), ("e.webp", WEBP)):
        r = tree({root + name: ("100644", data)})
        check(f"GREEN {name} with matching bytes is accepted", not r.problems and root + name in r.images,
              str(r.problems))
    ok, p = refused({root + "a.svg": ("100644", SVG)}, "not an allowed image")
    check("RED an .svg file is refused", ok, str(p))
    ok, p = refused({root + "a.png": ("100644", SVG)}, "not a PNG, JPEG")
    check("RED SVG bytes named .png are refused", ok, str(p))
    ok, p = refused({root + "a.png": ("100644", JPEG)}, "the name says png but the bytes are jpeg")
    check("RED JPEG bytes named .png are refused", ok, str(p))
    ok, p = refused({root + "a.png": ("100644", PNG + b"\x00" * (MAX_IMAGE_BYTES - len(PNG) + 1))},
                    "over the 3,145,728 byte limit")
    check("RED one byte over 3 MiB is refused", ok, str(p))
    r = tree({root + "a.png": ("100644", PNG + b"\x00" * (MAX_IMAGE_BYTES - len(PNG)))})
    check("GREEN exactly 3 MiB is accepted", not r.problems, str(r.problems))
    ok, p = refused({root + "a.png": ("100644", b"")}, "is empty")
    check("RED an empty file is refused", ok, str(p))
    for bad in ("Task-List.png", "task_list.png", "-task.png", "task list.png", "a//b.png", "../x.png",
                "a/.hidden.png"):
        ok, p = refused({root + bad: ("100644", PNG)}, "the name must be")
        check(f"RED the name {bad!r} is refused", ok, str(p))
    r = tree({root + "folder/sub-2/task-list-3.png": ("100644", PNG)})
    check("GREEN a nested lower-case name is accepted", not r.problems, str(r.problems))
    ok, p = refused({"screenshots/other/a.png": ("100644", PNG)}, f"only {ROOT} may hold files")
    check("RED an image outside screenshots/launchbrightly/ is refused", ok, str(p))
    ok, p = refused({root + "a.png": ("120000", b"../../secret")}, "not a regular file")
    check("RED a symlink is refused", ok, str(p))
    r = tree({root + "a.png": ("100755", PNG)})
    check("GREEN an executable bit on a real image is accepted", not r.problems, str(r.problems))

    print("Self-test: sidecars.")
    good = json.dumps({"title": "Tasks", "screen": "Tasks,  list view", "description": "The task list.",
                       "app_url": "https://go.tallyfy.com/tasks?filter=mine#top",
                       "captured_at": "2026-11-05T12:34:56.789Z", "recipe_id": 42,
                       "extra": "ignored"}).encode()
    r = tree({root + "a.png": ("100644", PNG), root + "a.json": ("100644", good)})
    f = r.sidecars.get(root + "a.png", {})
    check("GREEN a good sidecar is read", not r.problems and f.get("title") == "Tasks", str(r.problems))
    check("a sidecar value is folded to one line", f.get("screen") == "Tasks, list view", str(f))
    check("app_url keeps only the path of a tallyfy.com URL", f.get("app_url") == "/tasks", str(f))
    check("a numeric recipe_id is kept as text", f.get("recipe_id") == "42", str(f))
    check("an unknown key is ignored with a notice",
          "extra" not in f and any("'extra'" in n for n in r.notices), str(r.notices))
    r = tree({root + "a.png": ("100644", PNG),
              root + "a.json": ("100644", b'{"app_url": "/templates/abc?x=1"}')})
    check("app_url given as a path drops its query",
          r.sidecars.get(root + "a.png", {}).get("app_url") == "/templates/abc", str(r.sidecars))
    for label, body, needle in (
            ("another host", {"app_url": "https://evil.example/tasks"}, "is not on tallyfy.com"),
            ("a host that only ends in tallyfy.com", {"app_url": "https://eviltallyfy.com/x"},
             "is not on tallyfy.com"),
            ("plain http", {"app_url": "http://go.tallyfy.com/x"}, "is not on tallyfy.com"),
            ("a scheme-relative URL", {"app_url": "//evil.example/x"}, "is not on tallyfy.com"),
            ("a relative path", {"app_url": "tasks"}, "must be a path starting with /"),
            ("a date that is not ISO 8601", {"captured_at": "5 Nov 2026"}, "is not an ISO 8601"),
            ("an impossible date", {"captured_at": "2026-02-30"}, "is not an ISO 8601"),
            ("a number where text belongs", {"title": 7}, "title must be a string"),
            ("a boolean recipe_id", {"recipe_id": True}, "recipe_id must be a string")):
        ok, p = refused({root + "a.png": ("100644", PNG),
                         root + "a.json": ("100644", json.dumps(body).encode())}, needle)
        check(f"RED a sidecar with {label} is refused", ok, str(p))
    ok, p = refused({root + "a.png": ("100644", PNG), root + "a.json": ("100644", b"{not json")},
                    "is not valid UTF-8 JSON")
    check("RED a sidecar that is not JSON is refused", ok, str(p))
    ok, p = refused({root + "a.png": ("100644", PNG), root + "a.json": ("100644", b"[1, 2]")},
                    "must be a JSON object")
    check("RED a sidecar that is a JSON list is refused", ok, str(p))
    big = json.dumps({"description": "x" * MAX_SIDECAR_BYTES}).encode()
    ok, p = refused({root + "a.png": ("100644", PNG), root + "a.json": ("100644", big)},
                    "byte limit for a sidecar")
    check("RED a sidecar over 8 KB is refused", ok, str(p))
    ok, p = refused({root + "lonely.json": ("100644", b"{}")}, "beside exactly one image")
    check("RED a sidecar with no image is refused", ok, str(p))
    ok, p = refused({root + "a.png": ("100644", PNG), root + "a.jpg": ("100644", JPEG),
                     root + "a.json": ("100644", b"{}")}, "found 2")
    check("RED a sidecar two images could own is refused", ok, str(p))
    r = tree({root + "a.json": ("100644", b'{"title": "x"}')}, all_paths={root + "a.json", root + "a.png"})
    check("GREEN a sidecar pairs with an image elsewhere in the tree", not r.problems, str(r.problems))
    r = tree({root + "a.png": ("100644", PNG),
              root + "a.json": ("100644", b'{"captured_at": "2026-11-05T12:34:56.123456789+05:30"}')})
    check("GREEN captured_at with nanoseconds and an offset is accepted", not r.problems, str(r.problems))

    print("Self-test: keys, references and image lines.")
    sha = "0123456789abcdef" * 4
    check("derive_key puts the first 12 hex of the hash before the extension",
          derive_key(root + "a/b.png", sha) == "launchbrightly/a/b.0123456789ab.png",
          derive_key(root + "a/b.png", sha))
    raised = False
    try:
        derive_key("screenshots/other/a.png", sha)
    except ValueError:
        raised = True
    check("RED derive_key refuses a path outside the folder", raised)
    text = ("Intro\n\n![Task list](/screenshots/launchbrightly/tasks.png)\n\n"
            "```markdown\n![Example](/screenshots/launchbrightly/in-code.png)\n```\n\n"
            '<img src="/screenshots/launchbrightly/tag.png" alt="Tag alt" />\n'
            "See https://tallyfy.com/products/screenshots/old.png too.\n"
            "~~~~\n![x](/screenshots/launchbrightly/tilde.png)\n~~~~\n"
            "[a link](/screenshots/launchbrightly/linked%2Dfile.png).\n")
    refs = find_references(text)
    check("references are found with their alt text and line",
          refs == [("/screenshots/launchbrightly/tasks.png", 3, "Task list"),
                   ("/screenshots/launchbrightly/tag.png", 9, "Tag alt"),
                   ("/screenshots/launchbrightly/linked-file.png", 14, None)], str(refs))
    good_lines = ["![Task list](/screenshots/launchbrightly/tasks.png)",
                  "   1. ![Task list](https://screenshots.tallyfy.com/x/y.png)",
                  '- ![Task list](/screenshots/launchbrightly/a/b.png "The list")']
    for line in good_lines:
        check(f"GREEN image line {line!r}", bool(IMAGE_LINE_RE.match(line)))
    bad_lines = ["Some prose.", "![](/screenshots/launchbrightly/tasks.png)",
                 "![Task list](/screenshots/other/tasks.png)",
                 "![Task list](https://example.com/x.png)",
                 "![a](/screenshots/launchbrightly/x.png)![b](https://example.com/y.png)",
                 "![a](/screenshots/launchbrightly/x.png) and text",
                 "![{props.x}](/screenshots/launchbrightly/x.png)",
                 "![a <b>](/screenshots/launchbrightly/x.png)",
                 '<img src="/screenshots/launchbrightly/x.png" alt="x" />']
    for line in bad_lines:
        check(f"RED not an image line {line!r}", not IMAGE_LINE_RE.match(line))
    check("RED empty alt is a problem", alt_problem("  ") is not None)
    check("RED alt naming LaunchBrightly is a problem", alt_problem("Made by LaunchBrightly") is not None)
    check("GREEN plain alt is fine", alt_problem("Task list with due dates") is None)
    check("a line holding an image may be removed",
          all(REMOVABLE_LINE_RE.search(x) for x in ("", "   ", '<img src="x" />', "1. ![a](b)")))
    check("RED a prose line may not be removed", not REMOVABLE_LINE_RE.search("Click **Save**."))

    passed = sum(results)
    print(f"SELF-TEST {'PASSED' if passed == len(results) else 'FAILED'}: {passed} of {len(results)} case(s)")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    print(__doc__)
    sys.exit(2)
