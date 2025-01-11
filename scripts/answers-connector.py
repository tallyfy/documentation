import json
import os
import frontmatter
import argparse
import requests


def generate_file_hierarchy(current_file, root_directory):
	hierarchy = []

	current_directory = os.path.dirname(current_file)
	current_directory = current_directory.replace(root_directory, "")
	file_name = current_file.split('/')[-1]
	if file_name == "index.mdx":
		hierarchy_list = current_directory.split('/')
		hierarchy_list = [x.replace('-', ' ').replace('_', ' ').title() for x in hierarchy_list if x != '']
		result = [{}]
		for i, value in enumerate(hierarchy_list):
			result[0][f"lvl{i}"] = value
		hierarchy = result
	else:
		data = frontmatter.load(current_file)
		hierarchy_list = current_directory.split('/')
		hierarchy_list = [x.replace('-', ' ').replace('_', ' ').title() for x in hierarchy_list if x != '']
		try:
			hierarchy_list.append(data.metadata['title'])
		except:
			print(current_file)
		result = [{}]
		for i, value in enumerate(hierarchy_list):
			result[0][f"lvl{i}"] = value
		hierarchy = result

	return hierarchy[0]


TALLYFY_ANSWERS_BASE_URL = "https://answers.tallyfy.com"

# Create an argument parser
parser = argparse.ArgumentParser()

# Add the "--dir" flag/argument
parser.add_argument('--dir', type=str)

parser.add_argument('--collection_name', type=str)

parser.add_argument('--answers_api_key', type=str)

args = parser.parse_args()

dir_path = args.dir

collection_name = args.collection_name

ANSWERS_API_KEY = args.answers_api_key

print("Current dir:", dir_path)

EN_CONTENT_PATH = f"{dir_path}"

en_files_list = []
skip_list = ["404.mdx"]
for path, subdirs, files in os.walk(EN_CONTENT_PATH):
	for file in files:
		if file.endswith('.mdx') and file not in skip_list:
			en_files_list.append(path + '/' + file)

content = []
for file in en_files_list:
	data = frontmatter.load(file)
	url = file.split(EN_CONTENT_PATH)[1].split('.mdx')[0]
	if "index" in url:
		url = url.replace("index", '')

	hierarchy = generate_file_hierarchy(file, EN_CONTENT_PATH)
	depth = 0
	try:
		content.append(
			{"title": data.metadata['title'], "url": url, "content": str(data).replace("\n", " ").replace("#", ""),
			 "hierarchy": hierarchy,
			 "uid": data.metadata['id'], "source": hierarchy["lvl0"], "snippet": data.metadata['snippet']})
	except Exception as e:
		print("Couldn't send article:", url, data.metadata['title'], "- Please fix manually.")

with open('data.json', 'w') as f:
	json.dump(content, f)

# Upload JSON file
files = [
	('data', ('data.json', open("data.json", 'rb'), 'application/json'))
]

headers = {
	"Authorization": ANSWERS_API_KEY
}

resp = requests.post(f"{TALLYFY_ANSWERS_BASE_URL}/collections/{collection_name}/batch", files=files, headers=headers)

if resp.status_code == 200:
	print("Successful")
else:
	print(resp.json())
