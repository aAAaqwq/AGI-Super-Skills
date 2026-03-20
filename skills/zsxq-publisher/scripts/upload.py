#!/usr/bin/env python3
"""知识星球文件上传工具 - Upload files/images to a group."""

import argparse
import json
import os
import sys

import requests

BASE_URL = "https://api.zsxq.com"


def get_headers():
    token = os.environ.get("ZSXQ_ACCESS_TOKEN", "")
    if not token:
        config_path = os.path.expanduser("~/.config/zsxq/config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
                token = cfg.get("access_token", "")
    if not token:
        print("Error: ZSXQ_ACCESS_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Cookie": f"zsxq_access_token={token}",
    }


def upload_file(group_id, file_path, headers):
    """Upload a file to the group."""
    url = f"{BASE_URL}/v2/files/{group_id}/files"
    with open(file_path, "rb") as f:
        resp = requests.post(url, headers=headers, files={"file": f}, timeout=120)
    if resp.status_code == 200:
        data = resp.json().get("resp_data", {}).get("file", {})
        print(f"✅ File uploaded: {data.get('name', 'N/A')}")
        print(f"   file_key: {data.get('file_key', 'N/A')}")
        return data
    print(f"❌ Upload failed: HTTP {resp.status_code}", file=sys.stderr)
    return None


def upload_image(group_id, image_path, headers):
    """Upload an image to the group."""
    url = f"{BASE_URL}/v2/files/{group_id}/images"
    with open(image_path, "rb") as f:
        resp = requests.post(url, headers=headers, files={"file": f}, timeout=60)
    if resp.status_code == 200:
        data = resp.json().get("resp_data", {})
        print(f"✅ Image uploaded: {image_path}")
        print(f"   Dimensions: {data.get('width', '?')}x{data.get('height', '?')}")
        return data
    print(f"❌ Upload failed: HTTP {resp.status_code}", file=sys.stderr)
    return None


def list_files(group_id, headers, count=20):
    """List files in a group."""
    url = f"{BASE_URL}/v2/files/{group_id}/files?count={count}"
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 200:
        files = resp.json().get("resp_data", {}).get("files", [])
        print(f"Files in group ({len(files)}):")
        for f in files:
            name = f.get("name", "N/A")
            size = f.get("size", 0)
            print(f"  {name} ({size:,} bytes)")
        return files
    print(f"❌ List failed: HTTP {resp.status_code}", file=sys.stderr)
    return None


def main():
    parser = argparse.ArgumentParser(description="知识星球文件上传")
    parser.add_argument("--group-id", required=True, help="Group ID")
    parser.add_argument("--upload", help="File path to upload")
    parser.add_argument("--upload-image", help="Image path to upload")
    parser.add_argument("--list", action="store_true", help="List group files")
    parser.add_argument("--count", type=int, default=20, help="Number of files to list")
    args = parser.parse_args()

    headers = get_headers()

    if args.upload:
        upload_file(args.group_id, args.upload, headers)
    elif args.upload_image:
        upload_image(args.group_id, args.upload_image, headers)
    elif args.list:
        list_files(args.group_id, headers, args.count)
    else:
        parser.error("Provide --upload, --upload-image, or --list")


if __name__ == "__main__":
    main()
