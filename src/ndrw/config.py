"""Load and validate the entire configuration before contacting NextDNS."""

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """The configuration cannot be safely applied."""


@dataclass(frozen=True)
class Config:
    """Store a validated profile name and its desired rewrites.

    Attributes:
        profile: Name of the NextDNS profile to manage.
        rewrites: Validated rewrite records containing name and content fields.
    """

    profile: str
    rewrites: list[dict[str, str]]


class _UniqueKeyLoader(yaml.SafeLoader):
    """Reject repeated YAML keys instead of silently discarding values."""


def _construct_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode
) -> dict[str, object]:
    """Construct a YAML mapping while rejecting duplicate and non-string keys.

    Args:
        loader: Safe YAML loader constructing the configuration.
        node: YAML mapping node to convert into a dictionary.

    Returns:
        Mapping with unique string keys and their constructed values.

    Raises:
        ConfigError: If a key is repeated or is not a string.
    """
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str):
            raise ConfigError("Configuration keys must be strings.")
        if key in mapping:
            raise ConfigError(f"Duplicate YAML key: {key!r}.")
        mapping[key] = loader.construct_object(value_node)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def canonical_name(name: str) -> str:
    """Normalize a DNS name for case-insensitive record matching.

    Args:
        name: DNS name, optionally ending in a trailing dot.

    Returns:
        Lowercase name with one trailing dot removed.
    """
    return name.removesuffix(".").lower()


def _is_hostname(value: str, *, wildcard: bool = False) -> bool:
    """Check whether a value is a valid ASCII DNS hostname.

    Args:
        value: Hostname to validate, optionally ending in a trailing dot.
        wildcard: Whether to permit a leading wildcard label.

    Returns:
        Whether all labels and the full hostname satisfy DNS length and syntax limits.
    """
    hostname = canonical_name(value)
    if wildcard and hostname.startswith("*."):
        hostname = hostname[2:]
    if not hostname or len(hostname) > 253:
        return False
    return all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in hostname.split(".")
    )


def _is_content(value: str) -> bool:
    """Check whether rewrite content is an IP address or DNS hostname.

    Args:
        value: Rewrite target to validate.

    Returns:
        Whether the target is an IPv4 address, IPv6 address, or valid hostname.
    """
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        # Do not mistake an invalid IPv4 address for a hostname.
        return not re.fullmatch(r"[0-9.]+", value) and _is_hostname(value)


def load_config(path: Path) -> Config:
    """Load and validate a YAML configuration before any remote operations.

    Args:
        path: Path to the UTF-8 YAML configuration file.

    Returns:
        Validated profile name and rewrite records.

    Raises:
        ConfigError: If the file cannot be read, YAML is malformed, or any field
            fails validation, including duplicate YAML keys and rewrite names.
    """
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Cannot load configuration {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(
            "Configuration must be a YAML mapping, not an empty file or list."
        )
    if "profile_name" in raw:
        raise ConfigError("Rename 'profile_name' to 'profile' in your configuration.")
    if raw.keys() - {"profile", "rewrites"}:
        raise ConfigError(
            "Unknown configuration fields; expected 'profile' and 'rewrites'."
        )
    profile = raw.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        raise ConfigError("'profile' must be a non-empty profile name.")
    if "rewrites" not in raw or not isinstance(raw["rewrites"], list):
        raise ConfigError(
            "'rewrites' must be an explicit list (use [] for no rewrites)."
        )

    names = set()
    for index, rewrite in enumerate(raw["rewrites"], start=1):
        prefix = f"Rewrite {index}"
        if not isinstance(rewrite, dict) or rewrite.keys() != {"name", "content"}:
            raise ConfigError(f"{prefix} must contain exactly 'name' and 'content'.")
        for field in ("name", "content"):
            value = rewrite[field]
            if not isinstance(value, str) or not value or value != value.strip():
                raise ConfigError(
                    f"{prefix} '{field}' must be a non-empty string without surrounding whitespace."
                )
        if not _is_hostname(rewrite["name"], wildcard=True):
            raise ConfigError(
                f"{prefix} 'name' must be a valid DNS hostname (optionally starting with '*.')."
            )
        if not _is_content(rewrite["content"]):
            raise ConfigError(
                f"{prefix} 'content' must be an IPv4 address, IPv6 address, or DNS hostname."
            )
        name = canonical_name(rewrite["name"])
        if name in names:
            raise ConfigError(f"Duplicate rewrite name: {rewrite['name']!r}.")
        names.add(name)

    return Config(profile=profile.strip(), rewrites=raw["rewrites"])
