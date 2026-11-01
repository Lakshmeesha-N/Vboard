"""Tiny terminal chat for POST /v1/agent."""

import argparse
import json
import urllib.error
import urllib.request


def send(url: str, content: str) -> None:
    body = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/agent",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        print(f"error: HTTP {exc.code} {detail}")
        return
    except Exception as exc:
        print(f"error: server unreachable ({exc})")
        return

    print(payload.get("text", ""))
    print(
        f"[{status}] used_search={payload.get('used_search')} "
        f"rounds={payload.get('rounds')} note={payload.get('note')} "
        f"timing_ms={payload.get('timing_ms')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal chat for /v1/agent")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    while True:
        try:
            line = input("you> ")
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if line.strip() == "/quit":
            break
        send(args.url, line.replace("\\n", "\n"))


if __name__ == "__main__":
    main()
