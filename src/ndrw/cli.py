"""Command-line entry point."""

import argparse
import asyncio
import logging
import os
from importlib.metadata import version
from pathlib import Path

import aiohttp
from nextdns import ApiError, InvalidApiKeyError, NextDns

from ndrw.api import RewriteAPI
from ndrw.config import Config, ConfigError, load_config
from ndrw.sync import apply_changes, plan_changes


async def run(config: Config, api_key: str, *, dry_run: bool, prune: bool) -> None:
    """Read the selected profile and execute or preview its rewrite plan.

    Args:
        config: Validated profile name and desired rewrites.
        api_key: NextDNS API key used to authenticate the client.
        dry_run: Whether to report the plan without modifying remote records.
        prune: Whether to remove remote rewrites absent from the configuration.

    Raises:
        ConfigError: If the profile name does not identify exactly one profile.
        ApiError: If a NextDNS operation fails.
        InvalidApiKeyError: If authentication fails.
        aiohttp.ClientError: If an HTTP connection or response fails.
        TimeoutError: If a network operation times out.
    """
    async with aiohttp.ClientSession() as session:
        nextdns = await NextDns.create(session, api_key)
        profiles = await nextdns.get_profiles()
        matches = [profile for profile in profiles if profile["name"] == config.profile]
        if len(matches) != 1:
            raise ConfigError(
                f"Expected exactly one NextDNS profile named {config.profile!r}; found {len(matches)}."
            )
        profile = matches[0]
        logging.info("NextDNS profile: %s (ID: %s)", profile["name"], profile["id"])
        api = RewriteAPI(nextdns, profile["id"])
        existing = await api.list()
        changes = plan_changes(config.rewrites, existing, prune=prune)
        await apply_changes(api, changes, dry_run=dry_run)
        logging.info(
            "%s: %s change(s).",
            "Dry run complete" if dry_run else "Complete",
            len(changes),
        )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and apply the requested rewrite configuration.

    Args:
        argv: Arguments to parse, or None to use the process arguments.

    Returns:
        Zero on success, or one for configuration, authentication, or API errors.

    Raises:
        SystemExit: For help, version output, or invalid command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Manage NextDNS rewrites.")
    parser.add_argument("--version", action="version", version=version("ndrw"))
    parser.add_argument(
        "--config", required=True, type=Path, help="Path to YAML configuration file."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without modifying NextDNS (requires API access).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete remote rewrites absent from the configuration.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        config = load_config(args.config)
        api_key = os.getenv("NEXTDNS_API_KEY")
        if not api_key:
            raise ConfigError("NEXTDNS_API_KEY environment variable not set.")
        asyncio.run(run(config, api_key, dry_run=args.dry_run, prune=args.prune))
    except (
        ConfigError,
        ApiError,
        InvalidApiKeyError,
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ) as exc:
        logging.error("%s", exc)
        return 1
    return 0
