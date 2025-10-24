import argparse
import asyncio
import logging
import os
import yaml
import aiohttp

from nextdns import ApiError, InvalidApiKeyError, NextDns


async def create_rewrite(nextdns: NextDns, profile_id: str, rewrite: dict) -> str:
    """
    Create a new rewrite in the NextDNS API.

    Args:
        nextdns: The NextDNS client.
        profile_id: The ID of the profile to create the rewrite in.
        rewrite: The rewrite to create.

    Returns:
        str: The ID of the created rewrite.

    Raises:
        ApiError: If the rewrite creation fails.
    """
    try:
        response = await nextdns._http_request(
            method="POST",
            url=f"https://api.nextdns.io/profiles/{profile_id}/rewrites",
            data=rewrite,
        )
        return response["id"]
    except ApiError as e:
        raise ApiError(f"Error creating NextDNS rewrite: {str(e)}")


logging.basicConfig(level=logging.INFO, format="%(message)s")


async def main():
    parser = argparse.ArgumentParser(description="Manage NextDNS rewrites.")
    parser.add_argument(
        "--config", required=True, help="Path to YAML configuration file."
    )
    args = parser.parse_args()

    # Load YAML configuration file
    try:
        with open(args.config, "r") as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {args.config}")
        exit(1)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML configuration: {str(e)}")
        exit(1)
    except Exception as e:
        logging.error(f"Error loading configuration: {str(e)}")
        exit(1)

    # Get API key from environment variable
    api_key = os.getenv("NEXTDNS_API_KEY")
    if not api_key:
        logging.error("NEXTDNS_API_KEY environment variable not set.")
        exit(1)

    # Extract profile name from config
    profile_name = config.get("profile_name")
    if not profile_name:
        logging.error("NextDNS Profile Name not found in configuration file.")
        exit(1)
    else:
        logging.info(f"NextDNS Profile Name: {profile_name}")

    # Extract rewrites from config
    rewrites = config.get("rewrites", [])
    if not rewrites:
        logging.error("No NextDNS rewrites found in configuration file.")
        exit(1)

    async with aiohttp.ClientSession() as session:
        nextdns = await NextDns.create(session, api_key)

        # Get all profiles
        try:
            profiles = await nextdns.get_profiles()
        except ApiError as e:
            logging.error(f"Error getting NextDNS profile: {str(e)}")
            exit(1)

        # Find the profile in the list of profiles based on the name
        profile = next(
            (profile for profile in profiles if profile["name"] == profile_name), None
        )
        if not profile:
            logging.error(
                f"NextDNS profile name {profile_name} not found in list of profiles."
            )
            exit(1)
        else:
            logging.info(
                f"NextDNS profile found with name: {profile['name']} and ID: {profile['id']}."
            )

        # Get existing rewrites
        try:
            existing_rewrites = await nextdns._http_request(
                method="GET",
                url=f"https://api.nextdns.io/profiles/{profile['id']}/rewrites",
            )
        except ApiError as e:
            logging.error(f"Error getting existing NextDNS rewrites: {str(e)}")
            exit(1)

        for rewrite in rewrites:
            for existing_rewrite in existing_rewrites:
                if existing_rewrite["name"] == rewrite["name"]:
                    logging.info(
                        f"NextDNS rewrite {rewrite['name']} already exists. Ensuring it is up to date."
                    )
                    # There is no PUT or PATCH method for rewrites in the NextDNS API
                    # so we need to delete the existing rewrite and create a new one
                    try:
                        await nextdns._http_request(
                            method="DELETE",
                            url=f"https://api.nextdns.io/profiles/{profile['id']}/rewrites/{existing_rewrite['id']}",
                        )
                    except ApiError as e:
                        # Error code 204 means the rewrite was deleted successfully
                        if str(e) == "Error code: 204":
                            logging.info(f"NextDNS rewrite {rewrite['name']} deleted.")
                        else:
                            logging.error(f"Error deleting NextDNS rewrite: {str(e)}")
                            exit(1)
                    # Recreate the rewrite
                    try:
                        rewrite_id = await create_rewrite(
                            nextdns, profile["id"], rewrite
                        )
                        logging.info(
                            f"NextDNS rewrite {rewrite['name']} created with ID: {rewrite_id}."
                        )
                    except ApiError as e:
                        logging.error(f"Error creating NextDNS rewrite: {str(e)}")
                        exit(1)
                    break
            else:
                # The rewrite doesn't exist, so we need to create it
                logging.info(
                    f"NextDNS rewrite {rewrite['name']} does not exist. Creating..."
                )
                try:
                    rewrite_id = await create_rewrite(nextdns, profile["id"], rewrite)
                    logging.info(
                        f"NextDNS rewrite {rewrite['name']} created with ID: {rewrite_id}."
                    )
                except ApiError as e:
                    logging.error(f"Error creating NextDNS rewrite: {str(e)}")
                    exit(1)


if __name__ == "__main__":
    asyncio.run(main())
