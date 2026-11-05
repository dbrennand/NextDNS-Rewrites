import logging
from unittest.mock import AsyncMock

import aiohttp
import pytest
from nextdns import ApiError, InvalidApiKeyError

from ndrw import cli


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "profile: Main\nrewrites:\n  - name: example.com\n    content: 1.1.1.1\n"
    )
    return str(path)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEXTDNS_API_KEY", "test-key")
    client = AsyncMock()
    client.get_profiles.return_value = [{"name": "Main", "id": "profile-id"}]
    client._http_request.side_effect = [[], {"id": "created"}]
    monkeypatch.setattr(cli.NextDns, "create", AsyncMock(return_value=client))
    return client


def test_success(config_path, client):
    assert cli.main(["--config", config_path]) == 0
    cli.NextDns.create.assert_awaited_once()
    assert cli.NextDns.create.call_args.args[1] == "test-key"
    assert client._http_request.call_args_list[-1].kwargs["method"] == "POST"


def test_dry_run_prune_only_reads(config_path, client, caplog):
    caplog.set_level(logging.INFO)
    client._http_request.side_effect = [
        [
            {"name": "example.com", "content": "1.1.1.1", "id": "same"},
            {"name": "old.com", "content": "2.2.2.2", "id": "old"},
        ]
    ]
    assert cli.main(["--config", config_path, "--dry-run", "--prune"]) == 0
    client._http_request.assert_awaited_once_with(
        method="GET", url="https://api.nextdns.io/profiles/profile-id/rewrites"
    )
    assert "Would REPLACE example.com" in caplog.text
    assert "Would PRUNE old.com" in caplog.text


def test_invalid_config_does_not_contact_api(tmp_path, client, caplog):
    path = tmp_path / "bad.yaml"
    path.write_text("profile: Main\nrewrites: null")
    assert cli.main(["--config", str(path), "--prune"]) == 1
    cli.NextDns.create.assert_not_awaited()
    assert "explicit list" in caplog.text


def test_missing_key_does_not_contact_api(config_path, client, monkeypatch, caplog):
    monkeypatch.delenv("NEXTDNS_API_KEY")
    assert cli.main(["--config", config_path]) == 1
    cli.NextDns.create.assert_not_awaited()
    assert "NEXTDNS_API_KEY" in caplog.text


@pytest.mark.parametrize(
    "profiles", [[], [{"name": "Main", "id": "one"}, {"name": "Main", "id": "two"}]]
)
def test_missing_or_ambiguous_profile(config_path, client, caplog, profiles):
    client.get_profiles.return_value = profiles
    assert cli.main(["--config", config_path]) == 1
    client._http_request.assert_not_awaited()
    assert "Expected exactly one NextDNS profile" in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        ApiError("API failed"),
        InvalidApiKeyError("Invalid key"),
        aiohttp.ClientError("Connection failed"),
        TimeoutError("Timed out"),
    ],
)
def test_api_failures_return_nonzero(config_path, client, caplog, error):
    cli.NextDns.create.side_effect = error
    assert cli.main(["--config", config_path]) == 1
    assert str(error) in caplog.text


def test_list_failure_does_not_mutate(config_path, client):
    client._http_request.side_effect = ApiError("read failed")
    assert cli.main(["--config", config_path, "--prune"]) == 1
    assert client._http_request.await_count == 1


@pytest.mark.parametrize(
    "flag,expected", [("--help", "--prune"), ("--version", "2.0.0")]
)
def test_help_and_version(flag, expected, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([flag])
    assert exc.value.code == 0
    assert expected in capsys.readouterr().out


def test_config_argument_is_required():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2
