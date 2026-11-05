import asyncio
import logging
from unittest.mock import AsyncMock, call

import pytest
from nextdns import ApiError

from ndrw.sync import apply_changes, plan_changes

DESIRED = {"name": "example.com", "content": "1.1.1.1"}
EXISTING = {**DESIRED, "id": "existing"}
UNMANAGED = {"name": "other.com", "content": "2.2.2.2", "id": "other"}


def test_create_missing_and_preserve_unmanaged():
    changes = plan_changes([DESIRED], [UNMANAGED])
    assert [
        (change.operation, change.rewrite, change.existing_ids) for change in changes
    ] == [("create", DESIRED, ())]


@pytest.mark.parametrize("content", ["1.1.1.1", "2.2.2.2"])
def test_existing_record_is_always_replaced(content):
    changes = plan_changes([DESIRED], [{**EXISTING, "content": content}])
    assert len(changes) == 1
    assert changes[0].operation == "replace"
    assert changes[0].existing_ids == ("existing",)


def test_case_insensitive_matching_replaces_all_remote_duplicates():
    changes = plan_changes(
        [DESIRED],
        [EXISTING, {**EXISTING, "name": "Example.com.", "id": "duplicate"}],
        prune=True,
    )
    assert len(changes) == 1
    assert changes[0].existing_ids == ("existing", "duplicate")


def test_prune_only_unconfigured_names():
    changes = plan_changes([DESIRED], [EXISTING, UNMANAGED], prune=True)
    assert [change.operation for change in changes] == ["replace", "prune"]
    assert changes[1].existing_ids == ("other",)


def test_empty_config_without_prune_does_nothing():
    assert plan_changes([], [EXISTING]) == []


def test_empty_config_with_prune_deletes_everything():
    changes = plan_changes([], [EXISTING, UNMANAGED], prune=True)
    assert [change.operation for change in changes] == ["prune", "prune"]


@pytest.mark.parametrize("prune", [False, True])
def test_dry_run_never_mutates(api_mock, caplog, prune):
    caplog.set_level(logging.INFO)
    changes = plan_changes(
        [DESIRED, {"name": "new.com", "content": "::1"}],
        [EXISTING, UNMANAGED],
        prune=prune,
    )
    asyncio.run(apply_changes(api_mock, changes, dry_run=True))
    api_mock.delete.assert_not_awaited()
    api_mock.create.assert_not_awaited()
    assert "Would REPLACE example.com" in caplog.text
    assert "Would CREATE new.com" in caplog.text
    assert ("Would PRUNE other.com" in caplog.text) == prune


@pytest.fixture
def api_mock():
    api = AsyncMock()
    api.create.return_value = "created"
    return api


def test_apply_replaces_then_creates_then_prunes(api_mock):
    new = {"name": "new.com", "content": "::1"}
    changes = plan_changes([DESIRED, new], [EXISTING, UNMANAGED], prune=True)
    asyncio.run(apply_changes(api_mock, changes))
    assert api_mock.mock_calls == [
        call.delete("existing"),
        call.create(DESIRED),
        call.create(new),
        call.delete("other"),
    ]


def test_failed_recreation_stops_before_pruning(api_mock):
    api_mock.create.side_effect = ApiError("creation failed")
    changes = plan_changes([DESIRED], [EXISTING, UNMANAGED], prune=True)
    with pytest.raises(ApiError, match="creation failed"):
        asyncio.run(apply_changes(api_mock, changes))
    api_mock.delete.assert_awaited_once_with("existing")


def test_failed_delete_stops_before_create(api_mock):
    api_mock.delete.side_effect = ApiError("deletion failed")
    with pytest.raises(ApiError, match="deletion failed"):
        asyncio.run(apply_changes(api_mock, plan_changes([DESIRED], [EXISTING])))
    api_mock.create.assert_not_awaited()
