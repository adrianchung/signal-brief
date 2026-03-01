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
    args = parser.parse_args()

    config = Settings()

    if args.now:
        run_pipeline(config, args.provider)
    else:
        start(config, args.provider)


if __name__ == "__main__":
    main()
