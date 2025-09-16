import base64
import requests
import frontmatter
import argparse
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
OWNER = 'tallyfy'
REPO = 'documentation'
GITHUB_API_BASE = f'https://api.github.com/repos/{OWNER}/{REPO}/'
TALLYFY_ANSWERS_API_BASE = 'https://answers.tallyfy.com/collections/'
ANSWERS_API_KEY = None
def delete_object(uid, tallyfy_answers_api):
	"""
    Delete an object from the Tallyfy Answers API by its UID.
    """
	headers = {
		"Authorization": f"Bearer {ANSWERS_API_KEY}"
	}
	try:
		response = requests.delete(f'{tallyfy_answers_api}{uid}', headers=headers)
		if response.status_code == 200:
			logging.info(f"Successfully deleted object with UID: {uid}")
		else:
			logging.error(f"Failed to delete object with UID: {uid}. Status Code: {response.status_code}. Response: {response.json()}")
	except Exception as e:
		logging.exception(f"An error occurred while deleting object with UID: {uid}: {e}")

def fetch_github_data(url, headers):
	"""
    Fetch data from the GitHub API with the specified URL and headers.
    """
	try:
		response = requests.get(url, headers=headers)
		response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
		return response.json()
	except requests.exceptions.RequestException as e:
		logging.error(f"Error fetching data from GitHub API: {e}")
		sys.exit(1)

def decode_file_content(encoded_content):
	"""
    Decode base64-encoded file content.
    """
	try:
		return base64.b64decode(encoded_content).decode('utf-8')
	except Exception as e:
		logging.error(f"Failed to decode file content: {e}")
		return None

def main():
	# Argument parsing
	parser = argparse.ArgumentParser(description='Process removed files from a GitHub commit and delete related Tallyfy objects.')
	parser.add_argument('--commit_sha', required=True, type=str, help='Commit SHA')
	parser.add_argument('--collection_name', required=True, type=str, help='Tallyfy Answer collection name')
	parser.add_argument('--github_token', required=True, type=str, help='GitHub Personal Access Token')
	parser.add_argument('--answers_api_key', required=True, type=str, help='Tallyfy Answers API Key')

	args = parser.parse_args()

	global ANSWERS_API_KEY
	ANSWERS_API_KEY = args.answers_api_key

	# Variables
	commit_sha = args.commit_sha
	collection_name = args.collection_name
	github_token = args.github_token

	tallyfy_answers_api = f'{TALLYFY_ANSWERS_API_BASE}{collection_name}/objects/'
	committed_files_url = f'{GITHUB_API_BASE}commits/{commit_sha}'

	# Headers
	headers = {'Authorization': f'token {github_token}'}

	# Fetch committed files
	commit_data = fetch_github_data(committed_files_url, headers)
	commit_files = commit_data.get('files', [])
	
	# Get parent commit SHA to access file content before deletion
	parent_commits = commit_data.get('parents', [])
	if not parent_commits:
		logging.error("No parent commit found - cannot retrieve deleted file content")
		return
	
	parent_sha = parent_commits[0]['sha']
	logging.info(f"Using parent commit {parent_sha} to retrieve deleted file content")

	for file in commit_files:
		if file.get('status') == 'removed':
			logging.info(f"Found removed file: {file['filename']}")
			
			# Get file content from parent commit before deletion
			file_content_url = f"{GITHUB_API_BASE}contents/{file['filename']}?ref={parent_sha}"
			try:
				file_details = fetch_github_data(file_content_url, headers)
				encoded_content = file_details.get('content')

				if encoded_content:
					decoded_content = decode_file_content(encoded_content)
					if decoded_content:
						try:
							# Parse frontmatter metadata
							data = frontmatter.loads(decoded_content)
							uid = data.get('id')
							if uid:
								delete_object(uid, tallyfy_answers_api)
							else:
								logging.warning(f"No 'id' found in frontmatter metadata of file: {file['filename']}")
						except Exception as e:
							logging.error(f"Error parsing frontmatter for file: {file['filename']}: {e}")
					else:
						logging.error(f"Failed to decode content for removed file: {file['filename']}")
				else:
					logging.error(f"No content found in removed file: {file['filename']}")
			except Exception as e:
				logging.error(f"Error retrieving content for deleted file {file['filename']}: {e}")

if __name__ == '__main__':
	main()
