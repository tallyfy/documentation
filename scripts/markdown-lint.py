import yaml
import uuid
import re
import argparse
import os
from pathlib import Path

# Shiki-supported languages (subset of 200+ - these are commonly used)
# Full list: https://shiki.style/languages
SUPPORTED_LANGUAGES = {
    # Core web
    'javascript', 'js', 'typescript', 'ts', 'json', 'json5', 'jsonc',
    'html', 'css', 'scss', 'less', 'xml', 'yaml', 'yml', 'toml', 'ini',
    # Programming
    'python', 'py', 'java', 'kotlin', 'go', 'rust', 'c', 'cpp', 'csharp', 'cs',
    'ruby', 'rb', 'php', 'swift', 'scala', 'r', 'perl', 'lua', 'dart',
    # Shell/CLI
    'bash', 'sh', 'shell', 'zsh', 'fish', 'powershell', 'ps1', 'bat', 'cmd',
    # Web frameworks
    'jsx', 'tsx', 'vue', 'svelte', 'astro', 'mdx', 'markdown', 'md',
    # Data/Query
    'sql', 'graphql', 'csv', 'dax',
    # Config/DevOps
    'dockerfile', 'docker', 'nginx', 'apache', 'makefile', 'cmake',
    # Specialized
    'd2', 'mermaid', 'http', 'diff', 'git-commit', 'git-rebase',
    # Fallback/plain
    'text', 'txt', 'plain', 'ansi',
}


def validate_code_block_languages(content, file_path):
    """Check for unsupported code block languages."""
    # Find all code block language identifiers
    pattern = r'```(\w+(?:-\w+)*)'
    matches = re.findall(pattern, content)

    invalid_langs = []
    for lang in matches:
        if lang.lower() not in SUPPORTED_LANGUAGES:
            invalid_langs.append(lang)

    if invalid_langs:
        print(f"Unsupported code block language(s): {set(invalid_langs)}")
        print(f"  Use 'text' for plain output, or check https://shiki.style/languages")
        return False
    return True


def validate_mdx_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract frontmatter
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not frontmatter_match:
        print("Frontmatter not found or malformed.")
        return False

    frontmatter_text = frontmatter_match.group(1)
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        print(f"Error parsing frontmatter: {e}")
        return False

    # Validate frontmatter keys
    if 'id' not in frontmatter:
        print("Missing 'id' in frontmatter.")
        return False
    if 'sidebar' not in frontmatter or not isinstance(frontmatter['sidebar'], dict):
        print("Missing or invalid 'sidebar' in frontmatter.")
        return False
    if 'order' not in frontmatter['sidebar']:
        print("Missing 'order' in sidebar.")
        return False

    if frontmatter['id'] == '0000000000000000000000000000000000':
        print("'id' is not a valid UUID.")
        return False

    # Validate id is a valid UUID
    try:
        uuid.UUID(frontmatter['id'])
    except ValueError:
        print("'id' is not a valid UUID.")
        return False

    # Validate order is an integer >= 0
    order = frontmatter['sidebar']['order']
    if not isinstance(order, int) or order < 0:
        print("'order' must be an integer >= 0.")
        return False

    # Check the rest of the content
    rest_content = content[frontmatter_match.end():]

    required_imports = [
        'import { CardGrid, LinkTitleCard } from "~/components";',
        'import { CardGrid, LinkTitleCard, Steps } from "~/components";',
        'import { Steps, CardGrid, LinkTitleCard } from "~/components";'
    ]

    if not any(import_stmt in rest_content for import_stmt in required_imports):
        print("Missing required import statement.")
        return False
    # Check for the related articles section
    related_articles_pattern = r'## Related articles\s+<CardGrid>\s*(<LinkTitleCard[\s\S]*?)+</CardGrid>'
    if not re.search(related_articles_pattern, rest_content):
        print("Missing or malformed 'Related articles' section.")
        return False

    # Validate code block languages
    if not validate_code_block_languages(content, file_path):
        return False

    return True


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=str, required=True, help='Base directory path')
    args = parser.parse_args()
    # Validate directory
    base_dir = Path(args.dir)
    if not base_dir.is_dir():
        print(f"Invalid directory path: {args.dir}")
        return 1
    dir_path = args.dir
    files_list = []
    skip_list = ["404.mdx"]
    skip_dirs = ["src/content/docs/pro/changelog", "src/content/docs/changelog"]
    for path, subdirs, files in os.walk(dir_path):
        # Skip if path contains any directory from skip_dirs
        if not any(skip_dir in path for skip_dir in skip_dirs):
            for file in files:
                if file.endswith('.mdx') and file not in skip_list:
                    files_list.append(os.path.join(path, file))

    found_invalid_files = False
    for file in files_list:
        is_valid = validate_mdx_file(file)
        if not is_valid:
            found_invalid_files = True
            print("Invalid file:", file)
            print("-----------------------------------")
    if found_invalid_files:
        return 1
    else:
        return 0

if __name__ == "__main__":
    exit(main())