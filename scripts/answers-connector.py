#!/usr/bin/env python3
"""
Tallyfy Answers Connector

Converts MDX files to JSON objects and sends them to the Answers API.
Enhanced with proper validation, error handling, and malformed data prevention.
"""

import json
import os
import frontmatter
import argparse
import requests
import re
import uuid
import logging
from typing import Dict, List, Optional, Any
import sys

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s',
	handlers=[
		logging.FileHandler('answers-connector.log'),
		logging.StreamHandler(sys.stdout)
	]
)
logger = logging.getLogger(__name__)


def clean_markdown(markdown_content: str) -> str:
	"""
    Clean markdown content by removing Mermaid diagrams, code blocks, components, and formatting.

    Args:
        markdown_content: Raw markdown content to clean

    Returns:
        Cleaned markdown content as string with Mermaid diagram syntax removed
    """
	if not isinstance(markdown_content, str):
		logger.warning(f"Expected string for markdown content, got {type(markdown_content)}")
		return str(markdown_content) if markdown_content else ""

	content = markdown_content

	try:
		# Step 1: Remove Mermaid diagram blocks specifically (before general code block removal)
		mermaid_pattern = r'```mermaid[\s\S]*?```'
		content = re.sub(mermaid_pattern, '', content, flags=re.MULTILINE)

		# Step 2: Remove other code blocks (content within triple backticks)
		content = re.sub(r'```[^`]*```', '', content, flags=re.DOTALL)

		# Step 3: Remove TabItem blocks and their content
		tab_item_pattern = re.compile(r'<TabItem\s+label=[^>]*>(.*?)</TabItem>', re.DOTALL)
		content = re.sub(tab_item_pattern, '', content)

		# Step 4: Remove Tabs component if it exists
		tabs_pattern = re.compile(r'<Tabs>(.*?)</Tabs>', re.DOTALL)
		content = re.sub(tabs_pattern, '', content)

		# Step 5: Clean up import statements (including Astro imports)
		# Pattern 1: import { ... } from "...";
		import_pattern1 = re.compile(r'import\s+{[^}]*}\s+from\s+[\'"][^\'"]*[\'"];?', re.DOTALL)
		content = re.sub(import_pattern1, '', content)

		# Pattern 2: import ComponentName from "...";
		import_pattern2 = re.compile(r'import\s+\w+\s+from\s+[\'"][^\'"]*[\'"];?', re.DOTALL)
		content = re.sub(import_pattern2, '', content)

		# Pattern 3: import { ... } from '@astrojs/...';
		import_pattern3 = re.compile(r'import\s+{[^}]*}\s+from\s+[\'"]@[^\'"]*[\'"];?', re.DOTALL)
		content = re.sub(import_pattern3, '', content)

		# Pattern 4: import from relative paths like ~/components or @/components
		import_pattern4 = re.compile(r'import\s+.*\s+from\s+[\'"][~@/][^\'"]*[\'"];?', re.DOTALL)
		content = re.sub(import_pattern4, '', content)

		# Step 6: Clean up any leftover triple backticks
		content = re.sub(r'```.*', '', content)

		# Step 7: Remove HTML-style comments
		content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

		# Step 8: Clean up consecutive empty lines (including extra newlines from Mermaid removal)
		content = re.sub(r'\n{3,}', '\n\n', content)

		# Step 9: Remove "Related articles" section
		content = content.split("## Related articles")[0].rstrip()

		# Step 10: Additional cleanup
		content = content.replace("\n", " ").replace("#", "")
		content = ' '.join(content.split())  # Normalize whitespace

	except Exception as e:
		logger.error(f"Error cleaning markdown content: {e}")
		return markdown_content  # Return original if cleaning fails

	return content


def generate_file_hierarchy(file_path: str, root_directory: str) -> Dict[str, str]:
	"""
    Generate hierarchy information from file path.

    Args:
        file_path: Full path to the file
        root_directory: Root directory path

    Returns:
        Dictionary with hierarchy levels (lvl0, lvl1, etc.)
    """
	try:
		current_directory = os.path.dirname(file_path)
		current_directory = current_directory.replace(root_directory, "")
		file_name = os.path.basename(file_path)

		# Build hierarchy from directory structure
		hierarchy_list = current_directory.split('/')
		hierarchy_list = [
			x.replace('-', ' ').replace('_', ' ').title()
			for x in hierarchy_list if x
		]

		# Add title from frontmatter if not an index file
		if file_name != "index.mdx":
			try:
				file_data = frontmatter.load(file_path)
				if 'title' in file_data.metadata:
					hierarchy_list.append(file_data.metadata['title'])
				else:
					logger.warning(f"No title found in frontmatter for {file_path}")
			except Exception as e:
				logger.error(f"Error reading frontmatter for hierarchy in {file_path}: {e}")

		# Convert to hierarchy dictionary
		hierarchy_dict = {}
		for i, value in enumerate(hierarchy_list):
			if value and isinstance(value, str):  # Validate value
				hierarchy_dict[f"lvl{i}"] = value.strip()

		return hierarchy_dict

	except Exception as e:
		logger.error(f"Error generating hierarchy for {file_path}: {e}")
		return {"lvl0": "Unknown"}


def validate_article_data(article_data: Dict[str, Any], file_path: str) -> bool:
	"""
    Validate article data to prevent malformed JSON objects.

    Args:
        article_data: Dictionary containing article data
        file_path: Path to the source file for logging

    Returns:
        True if data is valid, False otherwise
    """
	required_fields = ['title', 'url', 'content', 'hierarchy', 'uid', 'source', 'snippet']

	for field in required_fields:
		if field not in article_data:
			logger.error(f"Missing required field '{field}' in {file_path}")
			return False

		if article_data[field] is None:
			logger.error(f"Field '{field}' is None in {file_path}")
			return False

	# Validate specific field types and constraints
	if not isinstance(article_data['title'], str) or not article_data['title'].strip():
		logger.error(f"Invalid title in {file_path}")
		return False

	if not isinstance(article_data['url'], str) or not article_data['url'].strip():
		logger.error(f"Invalid URL in {file_path}")
		return False

	if not isinstance(article_data['content'], str):
		logger.error(f"Invalid content type in {file_path}")
		return False

	if not isinstance(article_data['hierarchy'], dict):
		logger.error(f"Invalid hierarchy type in {file_path}")
		return False

	if not isinstance(article_data['uid'], str) or not article_data['uid'].strip():
		logger.error(f"Invalid UID in {file_path}")
		return False

	# Validate UID format (should be UUID-like)
	try:
		uuid.UUID(article_data['uid'])
	except ValueError:
		logger.error(f"Invalid UID format in {file_path}: {article_data['uid']}")
		return False

	if not isinstance(article_data['source'], str) or not article_data['source'].strip():
		logger.error(f"Invalid source in {file_path}")
		return False

	if not isinstance(article_data['snippet'], str):
		logger.error(f"Invalid snippet type in {file_path}")
		return False

	# Log content length for monitoring (but don't restrict)
	if len(article_data['content']) > 50000:  # Log if very long content
		logger.info(f"Long content ({len(article_data['content'])} chars) in {file_path}")

	if len(article_data['title']) > 200:
		logger.warning(f"Very long title ({len(article_data['title'])} chars) in {file_path}")

	return True


def process_mdx_file(file_path: str, root_directory: str) -> Optional[Dict[str, Any]]:
	"""
    Process a single MDX file and return article data.

    Args:
        file_path: Path to the MDX file
        root_directory: Root directory path

    Returns:
        Dictionary with article data or None if processing fails
    """
	try:
		# Load frontmatter
		try:
			data = frontmatter.load(file_path)
		except Exception as e:
			logger.error(f"Failed to load frontmatter from {file_path}: {e}")
			return None

		# Generate URL from file path
		url = file_path.split(root_directory)[1].split('.mdx')[0]
		if url.endswith("index"):
			url = url.replace("index", '')
		if not url.startswith('/'):
			url = '/' + url

		# Generate hierarchy
		hierarchy = generate_file_hierarchy(file_path, root_directory)

		# Clean content
		clean_content = clean_markdown(str(data.content))

		# Extract metadata with validation
		metadata = data.metadata

		# Required metadata fields
		if 'title' not in metadata or not metadata['title']:
			logger.error(f"Missing or empty title in {file_path}")
			return None

		if 'id' not in metadata or not metadata['id']:
			logger.error(f"Missing or empty ID in {file_path}")
			return None

		# Get source from hierarchy or default
		source = hierarchy.get('lvl0', 'Unknown')
		if source == 'Unknown':
			logger.warning(f"No source (lvl0) found for {file_path}, using 'Unknown'")

		# Get description/snippet
		snippet = metadata.get('description', '')
		if not snippet:
			# Generate snippet from content if not available
			words = clean_content.split()[:30]  # First 30 words
			snippet = ' '.join(words) + ('...' if len(words) == 30 else '')

		# Build article data
		article_data = {
			"title": str(metadata['title']).strip(),
			"url": str(url).strip(),
			"content": str(clean_content).strip(),
			"hierarchy": hierarchy,
			"uid": str(metadata['id']).strip(),
			"source": str(source).strip(),
			"snippet": str(snippet).strip()
		}

		# Validate the article data
		if not validate_article_data(article_data, file_path):
			return None

		logger.debug(f"Successfully processed {file_path}")
		return article_data

	except Exception as e:
		logger.error(f"Unexpected error processing {file_path}: {e}")
		return None


def upload_to_answers_api(content_list: List[Dict[str, Any]], collection_name: str, api_key: str, base_url: str) -> bool:
	"""
    Upload content to Answers API.

    Args:
        content_list: List of article data dictionaries
        collection_name: Name of the collection
        api_key: API key for authentication
        base_url: Base URL of the Answers API

    Returns:
        True if upload successful, False otherwise
    """
	try:
		# Validate inputs
		if not content_list:
			logger.error("No content to upload")
			return False

		if not collection_name or not api_key:
			logger.error("Missing collection name or API key")
			return False

		# Save to JSON file first
		json_filename = f'data_{collection_name}.json'
		try:
			with open(json_filename, 'w', encoding='utf-8') as f:
				json.dump(content_list, f, ensure_ascii=False, indent=2)
			logger.info(f"Saved {len(content_list)} articles to {json_filename}")
		except Exception as e:
			logger.error(f"Failed to save JSON file: {e}")
			return False

		# Upload to API
		files = [
			('data', (json_filename, open(json_filename, 'rb'), 'application/json'))
		]

		headers = {
			"Authorization": api_key
		}

		url = f"{base_url}/collections/{collection_name}/batch"
		logger.info(f"Uploading to {url}")

		response = requests.post(url, files=files, headers=headers, timeout=300)

		# Close file handle
		files[0][1][1].close()

		if response.status_code == 200:
			logger.info("Upload successful!")
			return True
		else:
			logger.error(f"Upload failed with status {response.status_code}")
			try:
				error_details = response.json()
				logger.error(f"Error details: {error_details}")
			except:
				logger.error(f"Response text: {response.text}")
			return False

	except Exception as e:
		logger.error(f"Error uploading to API: {e}")
		return False


def main():
	"""Main function to process MDX files and upload to Answers API."""

	# Parse command line arguments
	parser = argparse.ArgumentParser(
		description="Convert MDX files to JSON and upload to Tallyfy Answers API"
	)
	parser.add_argument('--dir', type=str, required=True, help='Directory containing MDX files')
	parser.add_argument('--collection_name', type=str, required=True, help='Collection name in Answers')
	parser.add_argument('--answers_api_key', type=str, required=True, help='Answers API key')
	parser.add_argument('--base_url', type=str, default='https://answers.tallyfy.com', help='Answers API base URL')
	parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

	args = parser.parse_args()

	if args.verbose:
		logging.getLogger().setLevel(logging.DEBUG)

	# Validate directory
	if not os.path.isdir(args.dir):
		logger.error(f"Directory does not exist: {args.dir}")
		sys.exit(1)

	logger.info(f"Processing directory: {args.dir}")
	logger.info(f"Collection: {args.collection_name}")

	# Find MDX files
	skip_list = ["404.mdx"]
	skip_dirs = ["src/content/docs/pro/changelog"]

	mdx_files = []
	for path, subdirs, files in os.walk(args.dir):
		# Skip if path contains any directory from skip_dirs
		if not any(skip_dir in path for skip_dir in skip_dirs):
			for file in files:
				if file.endswith('.mdx') and file not in skip_list:
					mdx_files.append(os.path.join(path, file))

	logger.info(f"Found {len(mdx_files)} MDX files to process")

	# Process files
	processed_content = []
	failed_files = []

	for file_path in mdx_files:
		article_data = process_mdx_file(file_path, args.dir)
		if article_data:
			processed_content.append(article_data)
		else:
			failed_files.append(file_path)

	logger.info(f"Successfully processed {len(processed_content)} files")
	if failed_files:
		logger.warning(f"Failed to process {len(failed_files)} files:")
		for failed_file in failed_files:
			logger.warning(f"  - {failed_file}")

	if not processed_content:
		logger.error("No content was successfully processed")
		sys.exit(1)

	# Upload to API
	success = upload_to_answers_api(
		processed_content,
		args.collection_name,
		args.answers_api_key,
		args.base_url
	)

	if success:
		logger.info("Process completed successfully!")
		sys.exit(0)
	else:
		logger.error("Upload failed")
		sys.exit(1)


if __name__ == "__main__":
	main()