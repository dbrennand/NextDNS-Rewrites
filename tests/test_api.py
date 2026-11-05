import asyncio
from unittest.mock import AsyncMock

import pytest
from nextdns import ApiError

from ndrw.api import RewriteAPI

URL = "https://api.nextdns.io/profiles/profile-id/rewrites"


def test_list():
    client = AsyncMock()
    client._http_request.return_value = [{"id": "rewrite-id"}]
    assert asyncio.run(RewriteAPI(client, "profile-id").list()) == [
        {"id": "rewrite-id"}
    ]
    client._http_request.assert_awaited_once_with(method="GET", url=URL)


def test_create():
    client = AsyncMock()
    client._http_request.return_value = {"id": "rewrite-id"}
    rewrite = {"name": "example.com", "content": "1.1.1.1"}
    assert asyncio.run(RewriteAPI(client, "profile-id").create(rewrite)) == "rewrite-id"
    client._http_request.assert_awaited_once_with(method="POST", url=URL, data=rewrite)


@pytest.mark.parametrize("error", [None, ApiError("Error code: 204")])
def test_delete_accepts_success_and_existing_204_workaround(error):
    client = AsyncMock()
    client._http_request.side_effect = error
    asyncio.run(RewriteAPI(client, "profile-id").delete("rewrite-id"))
    client._http_request.assert_awaited_once_with(
        method="DELETE", url=f"{URL}/rewrite-id"
    )


def test_delete_propagates_other_api_errors():
    client = AsyncMock()
    client._http_request.side_effect = ApiError("Error code: 403")
    with pytest.raises(ApiError, match="403"):
        asyncio.run(RewriteAPI(client, "profile-id").delete("rewrite-id"))
