"""Minimal AgentFlow python_script business node; no MetaAgent dependencies."""

import argparse
import json
import os


def respond(text: str) -> dict[str, str]:
    return {"response": "Echo: " + text}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.environ.get("AF_USER_TEXT", ""))
    args = parser.parse_args()
    print(json.dumps(respond(args.input), ensure_ascii=False))
