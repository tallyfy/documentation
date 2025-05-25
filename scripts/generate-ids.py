import argparse
import frontmatter
import os
import hashlib

def generate_object_id(obj):
	# Generate the MD5 hash of the string
	md5_hash = hashlib.md5(obj.encode()).hexdigest()
	return md5_hash


# Create an argument parser
parser = argparse.ArgumentParser(description='Process file names.')

# Add the "--files" flag/argument
parser.add_argument('--files', type=str, help='List of file names')

# Add the "--dir" flag/argument
parser.add_argument('--dir', type=str, help='Current dir path')

args = parser.parse_args()

file_names = args.files

dir_path = args.dir

new_files = str(file_names).split('\n')
skip_list = ["src/content/docs/404.mdx"]
for new_file in new_files:
	if not new_file.startswith("src/content/docs/pro/changelog") and new_file.endswith('.mdx') and new_file not in skip_list:
		f = dir_path + '/' + new_file
		data = frontmatter.load(f)
		obj_id = generate_object_id(data.content)
		data['id'] = obj_id
		data = frontmatter.dumps(data)
		with open(f, "w") as ff:
			ff.write(data)