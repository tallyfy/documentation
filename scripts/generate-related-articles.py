import os
import frontmatter
import requests
import argparse

RECOMMEND_ENDPOINT = 'https://answers.tallyfy.com/collections/tyfy/recommend/'

# Create an argument parser
parser = argparse.ArgumentParser()

# Add the "--dir" flag/argument
parser.add_argument('--dir', type=str)

parser.add_argument('--answers_api_key', type=str)

args = parser.parse_args()

dir_path = args.dir

ANSWERS_API_KEY = args.answers_api_key

ANSWERS_HEADERS = {
	'Authorization': ANSWERS_API_KEY
}


def get_recommendations(article_id):
	response = requests.get(RECOMMEND_ENDPOINT + article_id, headers=ANSWERS_HEADERS)
	if response.status_code == 200:
		data = response.json()['message']
		result = []
		for article in data:
			sorted_dict = {k: article['hierarchy'][k] for k in sorted(article['hierarchy'])}
			hierarchy = list(sorted_dict.values())
			header = ""
			for i in hierarchy[-2:-1]:
				header += i + " > "
			# header = header[:-3].replace('"', '')
			header += article['title'].replace('"', '')
			article_url = ""
			if not article['url'].endswith("/"):
				article_url = article['url'] + "/"
			else:
				article_url = article['url']
			result.append({"header": header,
						   "description": str(article['snippet']).replace('\n', '').replace('{', '[').replace('}', ']'),
						   "url": article_url})
		return result
	else:
		return None


print("Current dir:", dir_path)

EN_CONTENT_PATH = f"{dir_path}"

en_files_list = []
skip_list = ["404.mdx"]

skip_dirs = ["src/content/docs/pro/changelog"]
for path, subdirs, files in os.walk(EN_CONTENT_PATH):
	# Skip if path contains any directory from skip_dirs
	if not any(skip_dir in path for skip_dir in skip_dirs):
		for file in files:
			if file.endswith('.mdx') and file not in skip_list:
				en_files_list.append(os.path.join(path, file))


for file in en_files_list:
	if file.endswith('.mdx'):
		print(file)
		data = frontmatter.load(file)
		data.content = data.content.split("## Related articles")[0].rstrip()

		result = get_recommendations(data.metadata['id'])
		if result is not None:
			data.content += """

## Related articles
<CardGrid>
"""
			for article in result:
				data.content += '<LinkTitleCard header="<b>' + article["header"] + '</b>" href="/products' + article[
					"url"] + '" > ' + \
								article["description"] + ' </LinkTitleCard>' + "\r\n"
			data.content += """</CardGrid>"""
			data = frontmatter.dumps(data)
			with open(file, "w") as f:
				f.write(data)
		else:
			print("Error for article:", data.metadata['id'])
