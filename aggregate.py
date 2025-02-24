import json
import os
import shutil
import time
from os.path import dirname, abspath, isfile, isdir
import fnmatch
import argparse

from git import Repo

parser = argparse.ArgumentParser(description='Aggregate all protobuf files')
parser.add_argument('coin', type=str, help="Coin to parse from the .json file in the config folder")
parser.add_argument('-p', '--package_name', type=str, default="cosmospy_protobuf",
                    help="Name for the package to build. This will aggregate all files in the src/{package_name} folder")
args = parser.parse_args()


# https://stackoverflow.com/questions/52071642/python-copying-the-files-with-include-pattern
def include_patterns(*patterns):
    def _ignore_patterns(path, names):
        keep = set(name for pattern in patterns
                   for name in fnmatch.filter(names, pattern))
        ignore = set(name for name in names
                     if name not in keep and not isdir(os.path.join(path, name)))
        return ignore

    return _ignore_patterns


# Get current directory
d = dirname(abspath(__file__))

cache_dir = os.path.join(d, "repo_cache")
os.makedirs(cache_dir, exist_ok=True)

# Check if requested coin has a config
coin = args.coin
try:
    config_path = os.path.join(d, f'configs/{coin.lower()}.json')
    f = open(config_path, "r")
    coin_config = json.load(f)
    f.close()
except Exception:
    print("Coin couldn't be found")
    exit()

tmp_dir = os.path.join(d, "tmp")
if not os.path.isdir(tmp_dir):
    os.mkdir(tmp_dir)

project_dir = os.path.join(tmp_dir, str(time.time()))
os.mkdir(project_dir)

# Delete all existing protobuf files
root_dir = "src/" + args.package_name
root_abs_path = os.path.join(d, root_dir)
shutil.rmtree(root_abs_path, ignore_errors=True)
os.makedirs(root_abs_path, exist_ok=True)  # Create folder for package

for filename in os.listdir(root_abs_path):
    if filename == ".gitignore":
        continue

    file_path = os.path.join(root_abs_path, filename)
    try:
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
    except Exception as e:
        print('Failed to delete %s. Reason: %s' % (file_path, e))

# Load config
i = 1
for repo_url, repo_config in coin_config.items():
    branch = repo_config['branch']
    # Create a safe cache directory name using repo URL and branch
    safe_repo_name = repo_url.replace("://", "_").replace("/", "_")
    cache_repo_dir = os.path.join(cache_dir, f"{safe_repo_name}_{branch}")

    if not os.path.isdir(cache_repo_dir):
        print(f"Cloning {repo_url} | {branch}")
        Repo.clone_from(repo_url, cache_repo_dir, branch=branch)
    else:
        print(f"Using cached repo for {repo_url} | {branch}")

    # Optionally copy the cached repo to the temporary project folder if needed
    repo_dir = os.path.join(project_dir, str(i))
    shutil.copytree(cache_repo_dir, repo_dir, dirs_exist_ok=True)

    # Copy proto files from repo_dir as before
    for proto_folder in repo_config['paths']:
        proto_dir = os.path.join(repo_dir, proto_folder)
        proto_path_list = proto_folder.split('/')
        target = repo_config["target"] + "/" if "target" in repo_config else ""
        proto_path_in_repo = proto_path_list[-1]

        try:
            shutil.copytree(proto_dir, os.path.join(root_abs_path, (target if target else proto_path_in_repo)),
                            dirs_exist_ok=True, ignore=include_patterns("*.proto"))
            print(f"Copied {proto_path_in_repo}")
        except OSError as exc:
            try:
                proto_path_in_repo_for_file = target if target else "/".join(proto_path_in_repo.split('/')[:-1])
                os.makedirs(os.path.dirname(os.path.join(root_abs_path, proto_path_in_repo_for_file)), exist_ok=True)
                shutil.copy(proto_dir, os.path.join(root_abs_path, proto_path_in_repo_for_file))
                print(f"File {proto_dir} copied successfully")
            except:
                raise

    i += 1

tp_dir = os.path.join(d, "third_party")
for dirname in os.listdir(tp_dir):
    path = os.path.join(tp_dir, dirname)
    if os.path.isdir(path):
        shutil.copytree(path, os.path.join(root_abs_path, dirname), dirs_exist_ok=True)
