import argparse
import base64
import frontmatter
import json
import logging
import os
import re
import requests
from pathlib import Path
from typing import Optional

# Blacklist words that should never appear in AI-generated content
# Based on humanization guidelines - these words flag content as AI-generated
BLACKLIST_REPLACEMENTS = {
	'comprehensive': 'complete',
	'delve': 'explore',
	'delving': 'exploring',
	'navigate': 'use',
	'navigating': 'using',
	'landscape': 'field',
	'tapestry': 'mix',
	'multifaceted': 'complex',
	'pivotal': 'key',
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
	'meticulous': 'careful',
	'meticulously': 'carefully',
	'unwavering': 'steady',
	'underscore': 'highlight',
	'underscores': 'highlights',
	'underscoring': 'highlighting',
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
   meticulous, unwavering, underscore

2. BANNED TRANSITIONS (never start sentences with): Moreover, Furthermore, Indeed,
   Subsequently, Additionally

3. WORD REPLACEMENTS: Use "complete" not "comprehensive", "use" not "leverage",
   "smooth" not "seamless", "strong" not "robust", "help" not "facilitate"

4. STYLE: Write direct, conversational descriptions. Start with what Tallyfy does,
   not meta-commentary. Use active voice. Keep descriptions 200-350 characters.

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

	def generate_snippet(self, prompt: str, max_tokens: int = 100, temperature: float = 0.79) -> Optional[str]:
		"""Generate a snippet using Claude API."""
		try:
			payload = {
				"model": self.MODEL,
				"max_tokens": max_tokens,
				"system": self.system_prompt,
				"messages": [
					{"role": "user", "content": prompt}
				],
				"temperature": temperature
			}

			response = requests.post(
				self.BASE_API,
				headers=self.headers,
				json=payload,
				timeout=30
			)
			response.raise_for_status()

			return response.json()['content'][0]['text']

		except requests.exceptions.RequestException as e:
			logger.error(f"API request failed: {str(e)}")
			return None
		except (KeyError, IndexError) as e:
			logger.error(f"Failed to parse API response: {str(e)}")
			return None

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

		# Sanitize AI-generated content to remove blacklist words
		data['description'] = sanitize_ai_content(snippet)
		with open(file_path, "w", encoding='utf-8') as f:
			f.write(frontmatter.dumps(data))

		logger.info(f"Successfully updated snippet for: {file_path}")
		return True

	except Exception as e:
		logger.error(f"Error processing file {file_path}: {str(e)}")
		return False

def main():
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
