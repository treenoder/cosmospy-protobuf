import argparse
import json
import logging
import os
import re
import subprocess
import sys

# Parse command-line arguments: coin is required so we know which config to load,
# and package_name (defaults to your aggregated output folder)
parser = argparse.ArgumentParser(description="Compile aggregated protobuf files")
parser.add_argument("coin", type=str, help="Coin to parse from the config file in the configs folder")
parser.add_argument(
    "-p",
    "--package_name",
    type=str,
    default="cosmospy_protobuf",
    help="Name for the package to build. This will aggregate all files in the src/{package_name} folder",
)
args = parser.parse_args()

# Define the aggregated package path (output from aggregate.py)
package_dir = os.path.join("src", args.package_name)
absolute_package_path = os.path.abspath(package_dir)

# Load coin configuration so we can add extra proto include paths if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "configs", f"{args.coin.lower()}.json")
try:
    with open(config_path, "r") as f:
        coin_config = json.load(f)
except Exception as e:
    print(f"Error loading coin config: {e}")
    exit(1)

# Build a list of include paths.
# The base path is the aggregated package folder.
# If any repo config specifies a "target", we add that as an include directory.
proto_include_paths = [absolute_package_path]
for repo_config in coin_config.values():
    for raw_target in repo_config.get("paths", []):
        target = raw_target.strip("/").split("/")[-1]
        if target:
            target_path = os.path.join(absolute_package_path, target)
            if os.path.isdir(target_path):
                proto_include_paths.append(target_path)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s: %(message)s", level=logging.DEBUG
)

def run_protoc(filepath):
    # Build proto_path arguments: each include path is added separately
    proto_path_args = []
    for path in proto_include_paths:
        proto_path_args.append(f"--proto_path={path}")

    # For query.proto and service.proto we add grpc-specific options
    base = os.path.basename(filepath)
    if base in ("query.proto", "service.proto"):
        cmd = [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            *proto_path_args,
            "--python_out", package_dir,
            "--pyi_out", package_dir,
            "--grpc_python_out", package_dir,
            "--grpclib_python_out", package_dir,
            filepath,
        ]
        # logging.info(f"Compiling proto and grpc file: {filepath}")
    else:
        cmd = [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            *proto_path_args,
            "--python_out", package_dir,
            "--pyi_out", package_dir,
            filepath,
        ]
        # logging.info(f"Compiling proto file: {filepath}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error compiling {filepath}", exc_info=e)

def fix_proto_imports(filepath):
    # Build protoletariat command with the same include paths
    proto_path_args = []
    for path in proto_include_paths:
        proto_path_args.append(f"--proto-path={path}")

    cmd = [
        sys.executable,
        "-m",
        "protoletariat",
        "--create-package",
        "--in-place",
        "--python-out", package_dir,
        "--module-suffixes", "_pb2.py",
        "--module-suffixes", "_pb2.pyi",
        "--module-suffixes", "_pb2_grpc.py",
        "--module-suffixes", "_pb2_grpc.pyi",
        "--module-suffixes", "_grpc.py",
        "--module-suffixes", "_grpc.pyi",
        "protoc",
        *proto_path_args,
        filepath,
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error fixing imports for {filepath}", exc_info=e)

def walk_and_compile_proto(directory):
    logging.info(f"Compiling proto and grpc files: {directory}")
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".proto"):
                proto_file = os.path.abspath(os.path.join(root, filename))
                run_protoc(proto_file)

def walk_and_fix_imports(directory):
    logging.info(f"Fixing proto and grpc files: {directory}")
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".proto"):
                proto_file = os.path.abspath(os.path.join(root, filename))
                fix_proto_imports(proto_file)
                # logging.info(f"Fixed imports for {proto_file}")

def remove_compiled_files(directory):
    # Delete all previously generated Python files
    logging.info(f"Deleting compiled files: {directory}")
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".py") or filename.endswith(".pyi"):
                file_path = os.path.join(root, filename)
                os.remove(file_path)

if __name__ == "__main__":
    # Clean-up previously compiled files
    remove_compiled_files(package_dir)
    # Compile all .proto files in the aggregated output
    walk_and_compile_proto(package_dir)
    # Fix the proto imports according to our include paths
    walk_and_fix_imports(package_dir)
