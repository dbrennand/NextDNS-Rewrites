"""NextDNS rewrite operations, preserving the existing API workarounds."""

from nextdns import ApiError, NextDns


class RewriteAPI:
    """Access rewrite operations for a single NextDNS profile."""

    def __init__(self, client: NextDns, profile_id: str):
        """Bind the API adapter to a client and profile.

        Args:
            client: Authenticated NextDNS client.
            profile_id: ID of the profile whose rewrites will be managed.
        """
        self.client = client
        self.url = f"https://api.nextdns.io/profiles/{profile_id}/rewrites"

    async def list(self) -> list[dict]:
        """Fetch the profile's existing rewrites.

        Returns:
            Rewrite records returned by NextDNS, including their IDs.

        Raises:
            ApiError: If NextDNS rejects the request.
        """
        return await self.client._http_request(method="GET", url=self.url)

    async def create(self, rewrite: dict[str, str]) -> str:
        """Create a rewrite in the selected profile.

        Args:
            rewrite: DNS name and content to send to NextDNS.

        Returns:
            ID assigned to the created rewrite.

        Raises:
            ApiError: If NextDNS rejects the request.
        """
        response = await self.client._http_request(
            method="POST", url=self.url, data=rewrite
        )
        return response["id"]

    async def delete(self, rewrite_id: str) -> None:
        """Delete a rewrite, accepting the client's successful-204 exception.

        Args:
            rewrite_id: ID of the rewrite to delete.

        Raises:
            ApiError: If deletion fails with an error other than HTTP 204.
        """
        try:
            await self.client._http_request(
                method="DELETE", url=f"{self.url}/{rewrite_id}"
            )
        except ApiError as exc:
            # Keep the existing workaround: the client raises on successful 204s.
            if str(exc) != "Error code: 204":
                raise
