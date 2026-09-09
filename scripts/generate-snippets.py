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

class ClaudeClient:
	BASE_API = 'https://api.anthropic.com/v1/messages'
	MODEL = "claude-opus-4-6"

	def __init__(self, api_key: str, system_prompt: str):
		self.headers = {
			"anthropic-version": "2023-06-01",
			"x-api-key": api_key,
			"content-type": "application/json"
		}
		# Inject humanization guidelines into the system prompt
		self.system_prompt = system_prompt + HUMANIZATION_PROMPT_SUFFIX

	def generate_snippet(self, prompt: str, max_tokens: int = 100, temperature: float = 0.79, max_retries: int = 3) -> Optional[str]:
		"""Generate a snippet using Claude API with retry on transient failures."""
		payload = {
			"model": self.MODEL,
			"max_tokens": max_tokens,
			"system": self.system_prompt,
			"messages": [
				{"role": "user", "content": prompt}
			],
			"temperature": temperature
		}

		for attempt in range(1, max_retries + 1):
			try:
				response = requests.post(
					self.BASE_API,
					headers=self.headers,
					json=payload,
					timeout=60
				)
				response.raise_for_status()
				return response.json()['content'][0]['text']

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
			except (KeyError, IndexError) as e:
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
})


def _self_test() -> int:
	"""Prove the description post-processor goes RED and GREEN.

	Three RED arms feed it a banned character and require none back. One GREEN arm feeds
	it clean text and requires it back untouched, which a transform that mangled
	everything would fail while passing all three RED arms. Two further arms assert rules
	that have nothing to do with dashes, so the battery still proves the rest of the
	function runs rather than proving one regex fires.
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
	print(f"self-test OK: {len(seen)} cases. Dashes stripped, clean text untouched, other rules intact.")
	return 0


def main():
	# Checked before argparse: --self-test takes no API key and no file list.
	if '--self-test' in sys.argv:
		return _self_test()

	parser = argparse.ArgumentParser(description='Generate and update snippets for MDX files using Claude API')
	parser.add_argument('--files', type=str, required=True, help='Newline-separated list of files')
	parser.add_argument('--dir', type=str, required=True, help='Base directory path')
	parser.add_argument('--token', type=str, required=True, help='Claude API key')
	parser.add_argument('--prompt', type=str, required=True)

	args = parser.parse_args()

	# Validate directory
	base_dir = Path(args.dir)
	if not base_dir.is_dir():
		logger.error(f"Invalid directory path: {args.dir}")
		return 1

	try:
		system_prompt = base64.b64decode(args.prompt).decode('utf-8')
	except Exception as e:
		logger.error(f"Failed to decode prompt: {str(e)}")
		return 1

	claude_client = ClaudeClient(args.token, system_prompt)

	# Process files
	skip_list = {"src/content/docs/404.mdx"}
	files = [f.strip() for f in str(args.files).split('\n') if f.strip()]

	success_count = 0
	for file_name in files:
		if file_name.startswith("src/content/docs/pro/changelog") or not file_name.endswith('.mdx') or file_name in skip_list:
			logger.warning(f"Skipping file: {file_name}")
			success_count += 1
			continue

		file_path = base_dir / file_name
		if not file_path.is_file():
			logger.warning(f"File not found: {file_path}")
			continue

		if process_file(file_path, claude_client):
			success_count += 1

	total_files = len([f for f in files if f.endswith('.mdx') and f not in skip_list])
	logger.info(f"Processing complete. Successfully processed {success_count} out of {total_files} files.")

	return 0 if success_count == total_files else 1

if __name__ == "__main__":
	exit(main())
