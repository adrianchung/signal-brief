import argparse
import logging

from src.config import Settings
from src.pipeline import run_pipeline
from src.scheduler import start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="signal-brief: HN digest service")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the pipeline once immediately and exit",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "claude"],
        default="gemini",
        help="LLM provider to use for analysis (default: gemini)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and analyze stories but skip all delivery channels",
    )
    parser.add_argument(
        "--ignore-seen",
        action="store_true",
        help="Bypass cross-run deduplication (show all stories regardless of prior runs)",
    )
    args = parser.parse_args()

    config = Settings()

    if args.now or args.dry_run:
        run_pipeline(config, args.provider, dry_run=args.dry_run, ignore_seen=args.ignore_seen)
    else:
        start(config, args.provider)


if __name__ == "__main__":
    main()
