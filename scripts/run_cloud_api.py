"""Launch an isolated local API backed by Qdrant Cloud; never edits .env."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    os.environ["RAG_TARGET"] = "cloud"
    import uvicorn

    uvicorn.run("faq_agent.api:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
