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
        "--fallback-provider",
        choices=["gemini", "claude"],
        default=None,
        dest="fallback_provider",
        help="LLM provider to try if the primary provider fails (default: FALLBACK_PROVIDER env var)",
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
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help="Use a named schedule profile (e.g. morning, evening)",
    )
    parser.add_argument(
        "--history",
        metavar="N",
        nargs="?",
        const=10,
        type=int,
        help="Print the N most recent run summaries and exit (default: 10)",
    )
    args = parser.parse_args()

    config = Settings()

    import sys
    fallback = args.fallback_provider or config.fallback_provider

    if args.history is not None:
        from src.history import RunLogger
        RunLogger(config.history_path, config.history_retention_days).print_history(args.history)
    elif args.now or args.dry_run:
        profile = None
        if args.profile:
            from src.profiles import get_profile
            profile = get_profile(config, args.profile)
            if profile is None:
                print(f"Error: profile {args.profile!r} not found. Check SCHEDULE_<NAME> env vars.", file=sys.stderr)
                sys.exit(1)
        ok = run_pipeline(
            config, args.provider,
            fallback_provider=fallback,
            dry_run=args.dry_run,
            ignore_seen=args.ignore_seen,
            profile=profile,
        )
        if not ok:
            sys.exit(1)
    else:
        start(config, args.provider, fallback_provider=fallback)


if __name__ == "__main__":
    main()
