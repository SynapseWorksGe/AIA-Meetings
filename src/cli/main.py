"""CLI utility for AIA-Meetings (macOS / Linux)."""

import argparse
import json
import os
import sys
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
CONFIG_PATH = os.path.expanduser("~/.aia-meetings.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_client(args) -> tuple[httpx.Client, str]:
    config = load_config()
    base_url = args.url or config.get("base_url", DEFAULT_BASE_URL)
    api_key = args.key or config.get("api_key", "")

    if not api_key:
        print("Error: No API key. Run: aia-meetings configure --key YOUR_KEY")
        sys.exit(1)

    client = httpx.Client(
        base_url=base_url,
        headers={"X-API-Key": api_key},
        timeout=120.0,
    )
    return client, base_url


def cmd_configure(args):
    """Save configuration."""
    config = load_config()
    if args.key:
        config["api_key"] = args.key
    if args.url:
        config["base_url"] = args.url
    save_config(config)
    print(f"Configuration saved to {CONFIG_PATH}")
    if args.key:
        print(f"  API key: {args.key[:20]}...")
    if args.url:
        print(f"  Base URL: {args.url}")


def cmd_upload(args):
    """Upload an audio file."""
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    client, base_url = get_client(args)
    print(f"Uploading {file_path}...")

    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        data = {"language": args.language}
        if args.title:
            data["title"] = args.title

        response = client.post("/api/v1/meetings/upload", files=files, data=data)

    if response.status_code == 202:
        result = response.json()
        meeting_id = result["meeting_id"]
        print(f"Uploaded! Meeting ID: {meeting_id}")
        print(f"Status: {result['status']}")

        if args.wait:
            print("\nWaiting for processing to complete...")
            _wait_for_completion(client, meeting_id)
    else:
        print(f"Error ({response.status_code}): {response.text}")
        sys.exit(1)


def cmd_status(args):
    """Check meeting status."""
    client, _ = get_client(args)
    response = client.get(f"/api/v1/meetings/{args.meeting_id}")

    if response.status_code == 200:
        result = response.json()
        print(f"Meeting: {result.get('title', 'N/A')}")
        print(f"Status: {result['status']}")
        if result.get("error_message"):
            print(f"Error: {result['error_message']}")
    else:
        print(f"Error ({response.status_code}): {response.text}")


def cmd_result(args):
    """Get full meeting result."""
    client, _ = get_client(args)
    response = client.get(f"/api/v1/meetings/{args.meeting_id}")

    if response.status_code != 200:
        print(f"Error ({response.status_code}): {response.text}")
        sys.exit(1)

    result = response.json()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"\n{'='*60}")
    print(f"  {result.get('title', 'Без названия')}")
    print(f"  Status: {result['status']}")
    print(f"{'='*60}\n")

    if result["status"] != "done":
        print(f"Meeting is still processing ({result['status']})")
        return

    summary = result.get("summary")
    if summary:
        print("SUMMARY")
        print("-" * 40)
        print(summary.get("summary_text", ""))
        print()

        participants = summary.get("participants")
        if participants:
            print(f"PARTICIPANTS: {', '.join(participants)}")
            print()

        action_items = summary.get("action_items")
        if action_items:
            print("ACTION ITEMS")
            print("-" * 40)
            for i, item in enumerate(action_items, 1):
                line = f"  {i}. {item['task']}"
                if item.get("assignee"):
                    line += f" [{item['assignee']}]"
                if item.get("deadline"):
                    line += f" (до {item['deadline']})"
                print(line)
            print()

        decisions = summary.get("key_decisions")
        if decisions:
            print("KEY DECISIONS")
            print("-" * 40)
            for d in decisions:
                print(f"  * {d['decision']}")
                if d.get("context"):
                    print(f"    {d['context']}")
            print()

    transcript = result.get("transcript")
    if transcript and args.transcript:
        print("TRANSCRIPT")
        print("-" * 40)
        print(transcript.get("full_text", ""))
        print(f"\n({transcript.get('word_count', 0)} words)")


def cmd_list(args):
    """List meetings."""
    client, _ = get_client(args)
    response = client.get("/api/v1/meetings", params={"limit": args.limit})

    if response.status_code != 200:
        print(f"Error ({response.status_code}): {response.text}")
        sys.exit(1)

    data = response.json()
    meetings = data.get("meetings", [])
    total = data.get("total", 0)

    if not meetings:
        print("No meetings found.")
        return

    print(f"Meetings ({total} total):\n")
    for m in meetings:
        status_icon = {"done": "+", "error": "!", "uploading": "^", "transcribing": "~", "summarizing": "~"}.get(
            m["status"], "?"
        )
        date = m["created_at"][:16].replace("T", " ")
        title = m.get("title") or "Untitled"
        if len(title) > 40:
            title = title[:37] + "..."
        mid = m["id"][:8]
        print(f"  [{status_icon}] {mid}  {title}  ({date})")


def cmd_delete(args):
    """Delete a meeting."""
    client, _ = get_client(args)
    response = client.delete(f"/api/v1/meetings/{args.meeting_id}")

    if response.status_code == 204:
        print(f"Meeting {args.meeting_id} deleted.")
    else:
        print(f"Error ({response.status_code}): {response.text}")


def _wait_for_completion(client: httpx.Client, meeting_id: str, timeout: int = 600):
    """Poll until meeting is done or error."""
    start = time.time()
    prev_status = ""
    while time.time() - start < timeout:
        response = client.get(f"/api/v1/meetings/{meeting_id}")
        if response.status_code != 200:
            print(f"\nError checking status: {response.text}")
            return

        result = response.json()
        status = result["status"]

        if status != prev_status:
            print(f"  [{status}]", flush=True)
            prev_status = status

        if status == "done":
            print("\nProcessing complete!")
            cmd_result_data(result)
            return
        elif status == "error":
            print(f"\nError: {result.get('error_message', 'Unknown error')}")
            return

        time.sleep(5)

    print("\nTimeout waiting for completion.")


def cmd_result_data(result: dict):
    """Print result from dict (used by --wait)."""
    summary = result.get("summary")
    if summary:
        print(f"\nSummary: {summary.get('summary_text', '')[:200]}...")
        if summary.get("action_items"):
            print(f"Action items: {len(summary['action_items'])}")


def main():
    parser = argparse.ArgumentParser(prog="aia-meetings", description="AIA-Meetings CLI")
    parser.add_argument("--url", help="API base URL")
    parser.add_argument("--key", help="API key")

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # configure
    p_conf = subparsers.add_parser("configure", help="Save API key and URL")
    p_conf.add_argument("--key", dest="key", help="API key")
    p_conf.add_argument("--url", dest="url", help="Base URL")

    # upload
    p_upload = subparsers.add_parser("upload", help="Upload audio file")
    p_upload.add_argument("file", help="Path to audio file")
    p_upload.add_argument("--title", help="Meeting title")
    p_upload.add_argument("--language", default="ru", help="Language (default: ru)")
    p_upload.add_argument("--wait", action="store_true", help="Wait for processing to complete")

    # status
    p_status = subparsers.add_parser("status", help="Check meeting status")
    p_status.add_argument("meeting_id", help="Meeting ID")

    # result
    p_result = subparsers.add_parser("result", help="Get meeting result")
    p_result.add_argument("meeting_id", help="Meeting ID")
    p_result.add_argument("--json", action="store_true", help="Output as JSON")
    p_result.add_argument("--transcript", action="store_true", help="Include full transcript")

    # list
    p_list = subparsers.add_parser("list", help="List meetings")
    p_list.add_argument("--limit", type=int, default=10, help="Number of meetings")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a meeting")
    p_del.add_argument("meeting_id", help="Meeting ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "configure": cmd_configure,
        "upload": cmd_upload,
        "status": cmd_status,
        "result": cmd_result,
        "list": cmd_list,
        "delete": cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
