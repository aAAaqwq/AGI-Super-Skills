#!/usr/bin/env python3
"""知识星球发布脚本 - Talk/Q&A/Task posts via API."""

import argparse
import json
import os
import sys
import requests

BASE_URL = "https://api.zsxq.com"

def get_headers():
    token = os.environ.get("ZSXQ_ACCESS_TOKEN", "")
    if not token:
        # Try config file
        config_path = os.path.expanduser("~/.config/zsxq/config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
                token = cfg.get("access_token", "")
    if not token:
        print("Error: ZSXQ_ACCESS_TOKEN not set. See references/config.md", file=sys.stderr)
        sys.exit(1)
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Cookie": f"zsxq_access_token={token}",
    }

def check_auth(headers):
    """Verify token is valid by fetching user's groups."""
    resp = requests.get(f"{BASE_URL}/v2/groups", headers=headers, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        groups = data.get("resp_data", {}).get("group_list", [])
        print(f"✅ Auth OK — {len(groups)} groups accessible")
        for g in groups:
            print(f"   {g.get('group_name', 'N/A')} (ID: {g.get('group_id', 'N/A')})")
        return True
    elif resp.status_code == 401:
        print("❌ Token expired — re-login and update ZSXQ_ACCESS_TOKEN", file=sys.stderr)
    else:
        print(f"❌ Auth check failed: HTTP {resp.status_code}", file=sys.stderr)
    return False

def upload_image(headers, group_id, image_path):
    """Upload image and return upload_key, width, height."""
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        return None
    url = f"{BASE_URL}/v2/files/{group_id}/images"
    with open(image_path, "rb") as f:
        resp = requests.post(url, headers=headers, files={"file": f}, timeout=30)
    if resp.status_code == 200:
        data = resp.json().get("resp_data", {})
        print(f"✅ Image uploaded: {image_path}")
        return data
    print(f"❌ Image upload failed: HTTP {resp.status_code}", file=sys.stderr)
    return None

def upload_file(headers, group_id, file_path):
    """Upload file and return file_key."""
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return None
    url = f"{BASE_URL}/v2/files/{group_id}/files"
    with open(file_path, "rb") as f:
        resp = requests.post(url, headers=headers, files={"file": f}, timeout=60)
    if resp.status_code == 200:
        data = resp.json().get("resp_data", {}).get("file", {})
        print(f"✅ File uploaded: {file_path}")
        return data
    print(f"❌ File upload failed: HTTP {resp.status_code}", file=sys.stderr)
    return None

def publish_topic(headers, group_id, topic_type, text, title=None,
                  tags=None, images=None, file_path=None, deadline=None):
    """Publish a topic (talk/qa/task) to 知识星球."""
    type_map = {"talk": "talk", "qa": "q&a", "task": "task"}
    api_type = type_map.get(topic_type, topic_type)

    # Build topic payload
    topic = {"type": api_type, "text": text}
    if title:
        topic["title"] = title
    if tags:
        topic["text"] += f"\n\n#{' #'.join(tags)}"

    # Handle images
    if images:
        uploaded = []
        for img_path in images:
            result = upload_image(headers, group_id, img_path)
            if result:
                uploaded.append(result)
        if uploaded:
            topic["image_count"] = len(uploaded)
            topic["images"] = uploaded

    # Handle file attachment
    if file_path:
        file_data = upload_file(headers, group_id, file_path)
        if file_data:
            topic["file"] = file_data

    # Build request body
    body = {"req_data": {"topic": topic}}

    # Handle task deadline
    if api_type == "task" and deadline:
        body["req_data"]["task"] = {
            "owner_user_id": 0,
            "dead_line": deadline,
        }

    # Publish
    url = f"{BASE_URL}/v2/groups/{group_id}/topics"
    resp = requests.post(url, headers=headers, json=body, timeout=15)

    if resp.status_code == 200:
        data = resp.json()
        if data.get("succeeded"):
            topic_data = data.get("resp_data", {}).get("topic", {})
            topic_id = topic_data.get("id", "N/A")
            print(f"✅ Published [{api_type}] topic_id={topic_id}")
            return topic_id
        else:
            print(f"❌ Publish failed: {data}", file=sys.stderr)
    else:
        print(f"❌ Publish failed: HTTP {resp.status_code} — {resp.text[:200]}", file=sys.stderr)
    return None

def set_digest(headers, topic_id):
    """Set a topic as digest (精华). Star-owner only."""
    url = f"{BASE_URL}/v2/topics/{topic_id}/digest"
    resp = requests.post(url, headers=headers, timeout=10)
    if resp.status_code == 200:
        print(f"✅ Topic {topic_id} set as digest (精华)")
    else:
        print(f"❌ Set digest failed: HTTP {resp.status_code}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="知识星球发布工具")
    parser.add_argument("--check-auth", action="store_true", help="Check if token is valid")
    parser.add_argument("--type", choices=["talk", "qa", "task"], help="Post type")
    parser.add_argument("--group-id", help="Target group ID")
    parser.add_argument("--text", help="Post content text")
    parser.add_argument("--text-file", help="Read content from file")
    parser.add_argument("--title", help="Optional title")
    parser.add_argument("--tags", nargs="*", help="Tags (space-separated)")
    parser.add_argument("--image", nargs="*", help="Image file paths")
    parser.add_argument("--file", help="File attachment path")
    parser.add_argument("--deadline", help="Task deadline (YYYY-MM-DD HH:MM)")
    parser.add_argument("--digest", action="store_true", help="Set as digest after publish")
    parser.add_argument("--digest-only", help="Set existing topic as digest")
    args = parser.parse_args()

    headers = get_headers()

    if args.check_auth:
        check_auth(headers)
        return

    if args.digest_only:
        set_digest(headers, args.digest_only)
        return

    if not args.type or not args.group_id:
        parser.error("--type and --group-id are required")

    # Get text content
    text = args.text
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text = f.read()

    if not text:
        parser.error("--text or --text-file is required")

    topic_id = publish_topic(
        headers=headers,
        group_id=args.group_id,
        topic_type=args.type,
        text=text,
        title=args.title,
        tags=args.tags,
        images=args.image,
        file_path=args.file,
        deadline=args.deadline,
    )

    if topic_id and args.digest:
        set_digest(headers, topic_id)

if __name__ == "__main__":
    main()
