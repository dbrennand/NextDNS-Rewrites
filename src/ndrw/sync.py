"""Plan changes separately so dry runs use the same decisions as live runs."""

import logging
from dataclasses import dataclass
from typing import Literal

from ndrw.api import RewriteAPI
from ndrw.config import canonical_name


@dataclass(frozen=True)
class Change:
    """Describe a planned rewrite operation.

    Attributes:
        operation: Whether to create, replace, or prune the rewrite.
        rewrite: Desired record, or the existing record for a pruning operation.
        existing_ids: Remote record IDs to delete before any creation.
    """

    operation: Literal["create", "replace", "prune"]
    rewrite: dict[str, str]
    existing_ids: tuple[str, ...] = ()


def plan_changes(
    desired: list[dict[str, str]], existing: list[dict], *, prune: bool = False
) -> list[Change]:
    """Plan configured replacements and optional pruning without making API calls.

    Args:
        desired: Validated rewrites from the configuration.
        existing: Remote rewrites, including their IDs.
        prune: Whether to delete remote names absent from the configuration.

    Returns:
        Ordered changes, with configured creates and replacements before pruning.
        Existing configured records are replaced even when their content matches.
    """
    by_name = {}
    for rewrite in existing:
        by_name.setdefault(canonical_name(rewrite["name"]), []).append(rewrite)

    changes = []
    desired_names = {canonical_name(rewrite["name"]) for rewrite in desired}
    for rewrite in desired:
        matches = by_name.get(canonical_name(rewrite["name"]), [])
        # Replacement is intentional even when content is unchanged.
        changes.append(
            Change(
                "replace" if matches else "create",
                rewrite,
                tuple(match["id"] for match in matches),
            )
        )
    if prune:
        changes.extend(
            Change("prune", rewrite, (rewrite["id"],))
            for rewrite in existing
            if canonical_name(rewrite["name"]) not in desired_names
        )
    return changes


async def apply_changes(
    api: RewriteAPI, changes: list[Change], *, dry_run: bool = False
) -> None:
    """Apply a rewrite plan sequentially or log a preview without mutations.

    Args:
        api: API adapter for the selected profile.
        changes: Ordered rewrite operations to perform.
        dry_run: Whether to log planned operations without creating or deleting.

    Raises:
        nextdns.ApiError: If an operation fails. Processing stops immediately;
            completed changes are not rolled back.
    """
    for change in changes:
        description = f"{change.operation.upper()} {change.rewrite['name']} -> {change.rewrite['content']}"
        if dry_run:
            logging.info("[dry-run] Would %s", description)
            continue
        logging.info(description)
        for rewrite_id in change.existing_ids:
            await api.delete(rewrite_id)
        if change.operation != "prune":
            rewrite_id = await api.create(change.rewrite)
            logging.info("Created %s with ID: %s", change.rewrite["name"], rewrite_id)
