"""
generate-snippets.py - write a description for every documentation page that lacks one.

    python scripts/generate-snippets.py --dir=$PWD --token KEY --prompt BASE64
    python scripts/generate-snippets.py --dir=$PWD --dry-run        report only, no API call
    python scripts/generate-snippets.py --self-test [--target PATH]

WHOLE TREE, EVERY RUN (owner decision 218, 2026-10-03, tallyfy/documentation#296 criterion 2).
Until then it was handed the pages one commit added (`git diff-tree --diff-filter=A`), so a page
added in a push whose run was dropped from the concurrency queue never got a description, and a
new page that already had one written by its author had it overwritten. Now it reads the tree:
a page lacks a description when its front matter has no `description`, a null or blank one, or
a value that is not text (the CLAUDE.md template line `description: [AI-generated ...]` is a
YAML list). An existing description is never overwritten. pro/changelog/** and 404.mdx are left
alone, as before. Measured 2026-10-03 on staging 278b8bc7b: 0 of 593 pages lack one.

CAP: at most --max-pages pages (default 10) per run, in path order, because each is one Claude
API call. The run says how many wait for the next one.

EXIT CODES: 0 done (nothing to do included), 1 a description could not be written or a
self-test case failed, 2 could not run (no docs tree, unreadable front matter, bad arguments).
"""

import argparse
import base64
import frontmatter
import json
import logging
import os
import re
import sys
import time
import requests
from pathlib import Path
from typing import Optional

# Blacklist words that should never appear in AI-generated content
# Based on humanization guidelines - these words flag content as AI-generated
BLACKLIST_REPLACEMENTS = {
	# Tier 1 - worst offenders (200x+ AI frequency)
	'comprehensive': 'complete',
	'delve': 'explore',
	'delving': 'exploring',
	'navigate': 'use',
	'navigating': 'using',
	'landscape': 'field',
	'tapestry': 'mix',
	'multifaceted': 'complex',
	'pivotal': 'key',
	'meticulous': 'careful',
	'meticulously': 'carefully',
	'unwavering': 'steady',
	'underscore': 'highlight',
	'underscores': 'highlights',
	'underscoring': 'highlighting',
	'nuanced': 'specific',
	'intricate': 'detailed',
	'holistic': 'complete',
	'groundbreaking': 'new',
	'paradigm': 'model',
	'synergy': 'combination',
	'burgeoning': 'growing',
	'testament': 'proof',
	'poignant': 'notable',
	'embark': 'start',
	'foster': 'encourage',
	'harnessing': 'using',
	'beacon': 'example',
	'plethora': 'many',
	'bespoke': 'custom',
	'reimagine': 'rethink',
	'envision': 'imagine',
	'pinnacle': 'peak',
	'spearhead': 'lead',
	'commendable': 'good',
	# Tier 2 - high frequency (50-200x)
	'seamless': 'smooth',
	'seamlessly': 'smoothly',
	'robust': 'strong',
	'leverage': 'use',
	'leveraging': 'using',
	'leverages': 'uses',
	'facilitate': 'help',
	'facilitates': 'helps',
	'facilitating': 'helping',
	'paramount': 'important',
	'optimize': 'improve',
	'optimizes': 'improves',
	'optimizing': 'improving',
	'optimized': 'improved',
	'streamline': 'simplify',
	'streamlines': 'simplifies',
	'streamlining': 'simplifying',
	'streamlined': 'simplified',
	'empower': 'enable',
	'empowers': 'enables',
	'empowering': 'enabling',
	'ecosystem': 'suite',
	'stakeholder': 'team member',
	'stakeholders': 'team members',
	'actionable': 'practical',
	'cutting-edge': 'modern',
	'best-in-class': 'top',
	'transformative': 'major',
	'game-changer': 'breakthrough',
	'harness': 'use',
	'harnesses': 'uses',
	'elevate': 'improve',
	'elevates': 'improves',
	'orchestrate': 'coordinate',
	'orchestrates': 'coordinates',
	'orchestrating': 'coordinating',
	'orchestration': 'coordination',
	'bolster': 'strengthen',
	'bolsters': 'strengthens',
	'amplify': 'increase',
	'amplifies': 'increases',
}

# Transition words to remove or replace
TRANSITION_REPLACEMENTS = {
	'Moreover, ': '',
	'Furthermore, ': '',
	'Indeed, ': '',
	'Subsequently, ': 'Then, ',
	'Additionally, ': '',
}

# Patterns that indicate LLM prompt leakage - these should NEVER appear in generated content
PROMPT_LEAKAGE_PATTERNS = [
	r'Human:\s*End File',           # Cohere batch file markers
	r'llm-outputs/',                # Debug/temp file paths
	r'outputs-cohere',              # Cohere batch output markers
	r"Don't provide steps nor points",  # System prompt leakage
	r'summerize',                   # Common misspelling in prompts
	r'[\x00-\x08\x0b\x0c\x0e-\x1f]',  # Control characters (except newline, tab, CR)
	r'Generate a snippet',          # System prompt instructions
	r'You are tasked with',         # System prompt preamble
	r'Assistant:',                  # LLM role markers
]

def detect_prompt_leakage(text: str) -> bool:
	"""
	Detect if text contains LLM prompt artifacts or system instructions.

	Returns True if leakage patterns are found, False otherwise.
	These patterns indicate corrupted content from batch LLM processing
	that should not be saved to documentation files.
	"""
	if not text:
		return False

	for pattern in PROMPT_LEAKAGE_PATTERNS:
		if re.search(pattern, text, re.IGNORECASE):
			return True
	return False


def sanitize_ai_content(text: str) -> str:
	"""Remove/replace AI-typical words and phrases from generated content."""
	if not text:
		return text

	result = text

	# Replace blacklist words (case-insensitive)
	for bad_word, replacement in BLACKLIST_REPLACEMENTS.items():
		# Match word boundaries to avoid partial replacements
		pattern = re.compile(r'\b' + re.escape(bad_word) + r'\b', re.IGNORECASE)
		result = pattern.sub(replacement, result)

	# Replace transition phrases (case-sensitive for sentence starts)
	for phrase, replacement in TRANSITION_REPLACEMENTS.items():
		result = result.replace(phrase, replacement)

	return result

# Humanization guidelines to append to any AI prompt
HUMANIZATION_PROMPT_SUFFIX = """

CRITICAL WRITING RULES - Follow these exactly:

1. BANNED WORDS (never use): comprehensive, delve, navigate, landscape, tapestry,
   multifaceted, pivotal, seamless, robust, leverage, facilitate, paramount,
   meticulous, unwavering, underscore, nuanced, intricate, holistic, groundbreaking,
   paradigm, synergy, optimize, streamline, empower, ecosystem, stakeholder,
   actionable, cutting-edge, best-in-class, transformative, game-changer, harness,
   elevate, orchestrate, bolster, amplify, embark, foster, bespoke, reimagine

2. BANNED TRANSITIONS (never start sentences with): Moreover, Furthermore, Indeed,
   Subsequently, Additionally

2b. NO EM-DASHES OR EN-DASHES. Never use the characters — or –. Use a comma, a
   period, a colon, or a spaced hyphen instead. This is a hard rule in CLAUDE.md and
   is also stripped deterministically after generation, so producing one just gets
   rewritten.

3. WORD REPLACEMENTS: Use "complete" not "comprehensive", "use" not "leverage",
   "smooth" not "seamless", "strong" not "robust", "help" not "facilitate",
   "improve" not "optimize", "simplify" not "streamline", "enable" not "empower",
   "suite" not "ecosystem", "team member" not "stakeholder", "practical" not "actionable",
   "coordinate" not "orchestrate", "modern" not "cutting-edge"

4. STYLE: Write direct, conversational descriptions. Start with what Tallyfy does,
   not meta-commentary. Use active voice. Keep descriptions 200-350 characters,
   the range set under "Article Structure Rules" in CLAUDE.md.

5. NO FLUFF: Every word must add value. No empty benefit statements or vague promises.
"""

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_snippet_text(response_json: dict) -> Optional[str]:
	"""Return the text of the first `text` block in a Messages API response, or None.

	Claude Opus 5.5 always thinks, so a response can open with one or more `thinking`
	blocks before the answer. Reading `content[0]` would take a thinking block, whose
	`text` key does not exist. A response with no text block at all (a refusal, or
	thinking that used up max_tokens) and a text block holding only whitespace both
	return None, so the caller logs a failure and never writes an empty description.
	"""
	for block in response_json.get('content') or []:
		if block.get('type') == 'text':
			text = block.get('text') or ''
			return text if text.strip() else None
	return None


class ClaudeClient:
	BASE_API = 'https://api.anthropic.com/v1/messages'
	MODEL = "claude-opus-5-5"
	# Opus 5.5 rejects `temperature` with a 400 and always thinks. Effort is the one
	# control for how much it thinks. Its default is already medium; it is set here so
	# the choice is visible and does not move if the default does.
	EFFORT = "medium"

	def __init__(self, api_key: str, system_prompt: str, api_url: Optional[str] = None):
		self.api_url = api_url or self.BASE_API
		self.headers = {
			"anthropic-version": "2023-06-01",
			"x-api-key": api_key,
			"content-type": "application/json"
		}
		# Inject humanization guidelines into the system prompt
		self.system_prompt = system_prompt + HUMANIZATION_PROMPT_SUFFIX

	def generate_snippet(self, prompt: str, max_tokens: int = 16000, max_retries: int = 3) -> Optional[str]:
		"""Generate a snippet using Claude API with retry on transient failures.

		max_tokens is a ceiling, not a length target. Thinking counts toward it, so a small
		value cuts the answer off before it starts. Snippet length is set by the prompt and
		enforced afterwards by post_process_description.
		"""
		payload = {
			"model": self.MODEL,
			"max_tokens": max_tokens,
			"system": self.system_prompt,
			"messages": [
				{"role": "user", "content": prompt}
			],
			"output_config": {"effort": self.EFFORT}
		}

		for attempt in range(1, max_retries + 1):
			try:
				response = requests.post(
					self.api_url,
					headers=self.headers,
					json=payload,
					timeout=60
				)
				response.raise_for_status()
				body = response.json()
				text = extract_snippet_text(body)
				if text is None:
					logger.error(f"No text in API response (stop_reason={body.get('stop_reason')!r})")
				return text

			except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
				if attempt < max_retries:
					wait = attempt * 5
					logger.warning(f"Transient error (attempt {attempt}/{max_retries}), retrying in {wait}s: {e}")
					time.sleep(wait)
				else:
					logger.error(f"API request failed after {max_retries} attempts: {e}")
					return None
			except requests.exceptions.RequestException as e:
				logger.error(f"API request failed: {e}")
				return None
			except (KeyError, IndexError, ValueError, AttributeError) as e:
				logger.error(f"Failed to parse API response: {e}")
				return None

EM_DASH = '\u2014'
EN_DASH = '\u2013'


def strip_dashes(text: str) -> str:
	"""Replace em-dashes and en-dashes, which CLAUDE.md bans outright.

	The model is told not to produce them in HUMANIZATION_PROMPT_SUFFIX above. That
	reduces the rate and cannot be relied on, so this is the half that actually holds.
	Written after generate-snippets put an em-dash into a brand new article's
	description on the run that published it (tallyfy/documentation#220).

	Be precise about why nothing stopped it, because the obvious reading is wrong.
	`markdown-lint.py` genuinely never reads `description`. `ai-tell-check` DOES:
	`.github/ai-tells.txt` gives glyph-dash scope `both`, and a description carrying
	an em-dash returns rc 1 with an ERROR, against rc 0 for the same file with the
	dash removed. It passed on that one run purely on TIMING. `ai-tell-gate` checks
	out `workflow_run.head_sha`, which is the commit BEFORE this script rewrote the
	description, while `generate-snippets` checks out `head_branch`. So the gate is
	not blind to descriptions and must not be narrowed on that assumption. Left
	unfixed, the next full-corpus run would have gone red and blocked `sync`.

	A dash between digits is a numeric range, so it becomes a plain hyphen. Anywhere
	else it is separating an aside, so it becomes a spaced hyphen, which CLAUDE.md
	names as an allowed replacement.
	"""
	if not text:
		return text
	result = re.sub(r'(?<=\d)\s*[' + EM_DASH + EN_DASH + r']\s*(?=\d)', '-', text)
	result = re.sub(r'\s*[' + EM_DASH + EN_DASH + r']\s*', ' - ', result)
	return result


def post_process_description(text: str) -> str:
	"""Enforce description quality rules deterministically after AI generation.

	What this function actually does:
	- Strips leading/trailing whitespace and surrounding quotes
	- Replaces em-dashes and en-dashes, which CLAUDE.md bans (see strip_dashes)
	- Caps at 2 sentences
	- Ensures the text ends with a period
	- Truncates at 350 characters, at a word boundary where it can

	What it does NOT do, said explicitly because the docstring used to claim
	otherwise: there is no minimum length check and no padding. The 200 floor in
	CLAUDE.md is ADVISORY and is asked for in the generation prompt above; nothing
	enforces it here or anywhere else. `scripts/markdown-lint.py` never looks at
	`description`. The 350 ceiling is the only half that is enforced, and this
	truncation is where it happens.

	The range itself is stated in CLAUDE.md under "Article Structure Rules" and is
	deliberately not repeated here as a number, because two copies of it are how
	that file came to state two different ones (tallyfy/documentation#178).
	"""
	if not text:
		return text

	# Strip whitespace and surrounding quotes
	result = text.strip().strip('"').strip("'").strip()

	# Banned characters go first, so the 350-char check below measures the final text.
	result = strip_dashes(result)

	# Cap at 2 sentences: split on period-space or period-end, keep first 2
	sentences = re.split(r'(?<=\.)\s+', result)
	if len(sentences) > 2:
		result = ' '.join(sentences[:2])

	# Ensure ends with period
	if result and not result.endswith('.'):
		result = result.rstrip(',;:!?') + '.'

	# Truncate to 350 chars max (cut at last word boundary before limit)
	if len(result) > 350:
		truncated = result[:347]
		last_space = truncated.rfind(' ')
		if last_space > 200:
			result = truncated[:last_space].rstrip(',;:') + '...'
		else:
			result = truncated + '...'

	return result


def process_file(file_path: Path, claude_client: ClaudeClient) -> bool:
	"""Process a single MDX file and update its snippet."""
	try:
		logger.info(f"Processing file: {file_path}")
		data = frontmatter.load(file_path)

		if not data.content:
			logger.warning(f"Empty content in file: {file_path}")
			return False

		snippet = claude_client.generate_snippet(data.content)
		if snippet is None:
			logger.error(f"Failed to generate snippet for: {file_path}")
			return False

		# Check for prompt leakage in generated content
		if detect_prompt_leakage(snippet):
			logger.error(f"REJECTED: Prompt leakage detected in snippet for {file_path}")
			logger.error(f"Corrupted snippet preview: {snippet[:200]}...")
			return False

		# Sanitize AI-generated content to remove blacklist words, then enforce format rules
		data['description'] = post_process_description(sanitize_ai_content(snippet))
		with open(file_path, "w", encoding='utf-8') as f:
			f.write(frontmatter.dumps(data))

		logger.info(f"Successfully updated snippet for: {file_path}")
		return True

	except Exception as e:
		logger.error(f"Error processing file {file_path}: {str(e)}")
		return False

DOCS = os.path.join("src", "content", "docs")
SKIP_PREFIX = "src/content/docs/pro/changelog/"
SKIP_FILES = {"src/content/docs/404.mdx"}
DEFAULT_MAX_PAGES = 10


class CannotRun(Exception):
	"""Exit 2. Nothing has been written when this is raised."""


def lacks_description(metadata) -> bool:
	"""True when the front matter has no usable description: none, null, blank, or not text."""
	if "description" not in metadata:
		return True
	value = metadata.get("description")
	return not isinstance(value, str) or not value.strip()


def pages_lacking_description(root: str) -> list:
	"""Repository-relative paths of every eligible page lacking a description, sorted.
	Raises CannotRun when there is no docs tree or a page's front matter cannot be read."""
	base = os.path.join(root, DOCS)
	if not os.path.isdir(base):
		raise CannotRun(f"no {DOCS} under {root}")
	lacking, unreadable, seen = [], [], 0
	for folder, _, files in os.walk(base):
		for name in files:
			full = os.path.join(folder, name)
			rel = os.path.relpath(full, root).replace(os.sep, "/")
			if not rel.endswith(".mdx") or rel.startswith(SKIP_PREFIX) or rel in SKIP_FILES:
				continue
			seen += 1
			try:
				if lacks_description(frontmatter.load(full).metadata):
					lacking.append(rel)
			except Exception as e:
				unreadable.append(f"{rel}: {e}")
	if unreadable:
		raise CannotRun("front matter could not be read:\n  " + "\n  ".join(unreadable))
	if seen == 0:
		raise CannotRun(f"found no pages under {base}")
	logger.info(f"{seen} pages read, {len(lacking)} lack a description.")
	return sorted(lacking)


# The cases the self-test must run. Asserted as a SET, not just a pass/fail, because a
# battery that quietly stops testing something keeps printing green while getting weaker.
# Same reasoning as REQUIRED_RULE_IDS in ai-tell-check.py: adding a case needs a fixture,
# removing one has to be a code change with an author and a diff.
REQUIRED_SELF_TEST_CASES = frozenset({
	"em-dash-between-words",
	"en-dash-between-words",
	"en-dash-between-digits",
	"clean-text-unchanged",
	"two-sentence-cap-still-works",
	"trailing-period-still-added",
	"text-after-thinking-block",
	"no-text-block-is-failure",
	"blank-text-block-is-failure",
	"reconcile-writes-missing-description",
	"reconcile-blank-null-and-template-count-as-missing",
	"reconcile-never-overwrites-existing",
	"reconcile-skips-changelog-and-404",
	"reconcile-second-run-changes-nothing",
	"reconcile-cap-per-run",
	"reconcile-api-failure-writes-nothing",
	"reconcile-dry-run-writes-nothing",
})


def _self_test(target: str) -> int:
	"""Prove the description post-processor goes RED and GREEN.

	Three RED arms feed it a banned character and require none back. One GREEN arm feeds
	it clean text and requires it back untouched, which a transform that mangled
	everything would fail while passing all three RED arms. Two further arms assert rules
	that have nothing to do with dashes, so the battery still proves the rest of the
	function runs rather than proving one regex fires.

	Three more arms cover extract_snippet_text: the text block is found behind a thinking
	block, and a response with no text block or only a blank one returns None rather than
	an empty description.
	"""
	failures = []
	seen = set()

	def check(case_id, ok, got):
		seen.add(case_id)
		if not ok:
			failures.append(f"{case_id}: got {got!r}")

	def clean_of_dashes(s):
		return EM_DASH not in s and EN_DASH not in s

	r = post_process_description(f"Tallyfy works out dates at launch {EM_DASH} so templates stay reusable.")
	check("em-dash-between-words", clean_of_dashes(r) and " - " in r, r)

	r = post_process_description(f"Tallyfy works out dates at launch {EN_DASH} so templates stay reusable.")
	check("en-dash-between-words", clean_of_dashes(r) and " - " in r, r)

	r = post_process_description(f"Descriptions run 200{EN_DASH}350 characters.")
	check("en-dash-between-digits", clean_of_dashes(r) and "200-350" in r, r)

	clean = "Tallyfy turns template rules into real dates when you launch a process."
	r = post_process_description(clean)
	check("clean-text-unchanged", r == clean, r)

	r = post_process_description("One. Two. Three.")
	check("two-sentence-cap-still-works", r == "One. Two.", r)

	r = post_process_description("No trailing period here")
	check("trailing-period-still-added", r.endswith("."), r)

	# Response parsing. Opus 5.5 can put thinking blocks before the answer, so the
	# snippet is the first text block, and a response without usable text is a failure.
	thinking = {"type": "thinking", "thinking": "", "signature": "x"}
	r = extract_snippet_text({"content": [thinking, {"type": "text", "text": clean}]})
	check("text-after-thinking-block", r == clean, r)

	r = extract_snippet_text({"content": [thinking], "stop_reason": "max_tokens"})
	check("no-text-block-is-failure", r is None, r)

	r = extract_snippet_text({"content": [thinking, {"type": "text", "text": "  "}]})
	check("blank-text-block-is-failure", r is None, r)

	# Whole-tree reconcile (owner decision 218). These drive the CLI of `target`, against a fake
	# Messages API on 127.0.0.1, so the real request code runs and the same cases can be pointed
	# at an older copy of this script to see which of them it fails.
	_reconcile_cases(target, check)

	missing = REQUIRED_SELF_TEST_CASES - seen
	unexpected = seen - REQUIRED_SELF_TEST_CASES
	if missing or unexpected:
		print(f"SELF-TEST BROKEN: the case set drifted. missing={sorted(missing)} unexpected={sorted(unexpected)}")
		return 2
	if failures:
		print("SELF-TEST FAILED:")
		for f in failures:
			print(f"  {f}")
		return 1
	print(f"self-test OK: {len(seen)} cases. Dashes stripped, clean text untouched, other rules intact, response parsing picks the text block.")
	return 0


def _reconcile_cases(target, check):
	import subprocess
	import tempfile
	import threading
	from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

	generated = "Tallyfy self-test description for a page that had none."
	state = {"calls": 0, "fail": False}

	class FakeMessages(BaseHTTPRequestHandler):
		def log_message(self, *a):
			pass

		def do_POST(self):
			self.rfile.read(int(self.headers.get("Content-Length") or 0))
			state["calls"] += 1
			if state["fail"]:
				code, body = 500, {"type": "error", "error": {"type": "api_error"}}
			else:
				code, body = 200, {"content": [{"type": "text", "text": generated}], "stop_reason": "end_turn"}
			data = json.dumps(body).encode()
			self.send_response(code)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(data)))
			self.end_headers()
			self.wfile.write(data)

	server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMessages)
	threading.Thread(target=server.serve_forever, daemon=True).start()
	api = f"http://127.0.0.1:{server.server_address[1]}/v1/messages"
	prompt = base64.b64encode(b"You write page descriptions.").decode()

	def page(root, rel, front, body="Body.\n"):
		path = os.path.join(root, rel)
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w", encoding="utf-8") as fh:
			fh.write("---\n" + front + "---\n\n" + body)

	def run(root, *extra):
		r = subprocess.run([sys.executable, target, f"--dir={root}", "--token=self-test",
		                    f"--prompt={prompt}", f"--api-url={api}", *extra],
		                   capture_output=True, text=True)
		return r.returncode, r.stdout + r.stderr

	def desc(root, rel):
		return frontmatter.load(os.path.join(root, rel)).get("description")

	def snapshot(root):
		out = {}
		for folder, _, files in os.walk(root):
			for name in files:
				with open(os.path.join(folder, name), "rb") as fh:
					out[os.path.join(folder, name)] = fh.read()
		return out

	try:
		with tempfile.TemporaryDirectory() as tmp:
			d = os.path.join(tmp, "repo")
			page(d, "src/content/docs/pro/none.mdx", "title: None\n")
			page(d, "src/content/docs/pro/blank.mdx", "description: '   '\ntitle: Blank\n")
			page(d, "src/content/docs/pro/null.mdx", "description:\ntitle: Null\n")
			page(d, "src/content/docs/pro/template.mdx", "description: [AI-generated comprehensive description]\ntitle: T\n")
			page(d, "src/content/docs/pro/has.mdx", "description: An author wrote this one.\ntitle: Has\n")
			page(d, "src/content/docs/pro/changelog/2026/c.mdx", "title: C\n")
			page(d, "src/content/docs/404.mdx", "title: N\n")
			before = snapshot(d)
			rc, out = run(d)
			check("reconcile-writes-missing-description",
			      rc == 0 and desc(d, "src/content/docs/pro/none.mdx") == generated, (rc, out[-300:]))
			got = [desc(d, f"src/content/docs/pro/{n}.mdx") for n in ("blank", "null", "template")]
			check("reconcile-blank-null-and-template-count-as-missing", got == [generated] * 3, got)
			has = os.path.join(d, "src/content/docs/pro/has.mdx")
			check("reconcile-never-overwrites-existing", snapshot(d)[has] == before[has],
			      desc(d, "src/content/docs/pro/has.mdx"))
			after = snapshot(d)
			check("reconcile-skips-changelog-and-404",
			      all(after[os.path.join(d, p)] == before[os.path.join(d, p)]
			          for p in ("src/content/docs/pro/changelog/2026/c.mdx", "src/content/docs/404.mdx")), "changed")
			calls = state["calls"]
			rc, out = run(d)
			check("reconcile-second-run-changes-nothing",
			      rc == 0 and snapshot(d) == after and state["calls"] == calls, (rc, state["calls"] - calls))

		with tempfile.TemporaryDirectory() as tmp:
			d = os.path.join(tmp, "repo")
			for i in range(3):
				page(d, f"src/content/docs/pro/p{i}.mdx", "title: P\n")
			rc, out = run(d, "--max-pages=2")
			got = [desc(d, f"src/content/docs/pro/p{i}.mdx") for i in range(3)]
			check("reconcile-cap-per-run",
			      rc == 0 and got == [generated, generated, None] and "1 more page(s) lack a description" in out,
			      (rc, got))

		with tempfile.TemporaryDirectory() as tmp:
			d = os.path.join(tmp, "repo")
			page(d, "src/content/docs/pro/none.mdx", "title: None\n")
			before = snapshot(d)
			state["fail"] = True
			rc, out = run(d)
			state["fail"] = False
			check("reconcile-api-failure-writes-nothing", rc == 1 and snapshot(d) == before, rc)
			calls = state["calls"]
			rc, out = run(d, "--dry-run")
			check("reconcile-dry-run-writes-nothing",
			      rc == 0 and snapshot(d) == before and state["calls"] == calls and "1 lack a description" in out,
			      (rc, out[-200:]))
	finally:
		server.shutdown()


def main():
	# Checked before argparse: --self-test takes no API key and no tree.
	if '--self-test' in sys.argv:
		argv = sys.argv[1:]
		target = os.path.abspath(__file__)
		if '--target' in argv and argv.index('--target') + 1 < len(argv):
			target = os.path.abspath(argv[argv.index('--target') + 1])
		return _self_test(target)

	parser = argparse.ArgumentParser(description='Write a description for every page that lacks one, using the Claude API')
	parser.add_argument('--dir', type=str, required=True, help='Repository root (the folder holding src/content/docs)')
	parser.add_argument('--token', type=str, help='Claude API key')
	parser.add_argument('--prompt', type=str, help='System prompt, base64')
	parser.add_argument('--max-pages', type=int, default=DEFAULT_MAX_PAGES)
	parser.add_argument('--dry-run', action='store_true')
	parser.add_argument('--api-url', type=str, default=None, help=argparse.SUPPRESS)

	args = parser.parse_args()
	if args.max_pages < 1 or (not args.dry_run and not (args.token and args.prompt)):
		logger.error("CANNOT RUN: pass --token and --prompt (or --dry-run), and --max-pages of 1 or more")
		return 2

	try:
		lacking = pages_lacking_description(os.path.abspath(args.dir))
	except CannotRun as e:
		print(f"::error::generate-snippets could not run, so nothing was written: {e}", flush=True)
		return 2

	todo, later = lacking[:args.max_pages], lacking[args.max_pages:]
	for rel in todo:
		logger.info(f"  lacks a description: {rel}")
	if later:
		print(f"::warning::{len(later)} more page(s) lack a description and wait for a later run "
		      f"(cap {args.max_pages} per run). First: {later[0]}", flush=True)
	if args.dry_run or not todo:
		logger.info(f"{'DRY RUN: would write' if args.dry_run else 'Nothing to write:'} {len(todo)} description(s) this run.")
		return 0

	try:
		system_prompt = base64.b64decode(args.prompt).decode('utf-8')
	except Exception as e:
		logger.error(f"Failed to decode prompt: {str(e)}")
		return 2

	claude_client = ClaudeClient(args.token, system_prompt, api_url=args.api_url)
	success_count = 0
	for rel in todo:
		if process_file(Path(args.dir) / rel, claude_client):
			success_count += 1

	logger.info(f"Processing complete. Wrote {success_count} of {len(todo)} description(s) this run.")
	return 0 if success_count == len(todo) else 1

if __name__ == "__main__":
	exit(main())
