# NextDNS Rewrites

Manage NextDNS rewrites.

A Python script to manage NextDNS rewrites by ensuring they match the desired state defined in a YAML configuration file.

## Overview

This tool synchronises your NextDNS profile's rewrites with a local configuration file. It automatically creates missing rewrites and updates existing ones to match your desired state. Since the NextDNS API doesn't provide PUT or PATCH methods for rewrites, the script achieves updates by deleting and recreating existing rewrites.

## Prerequisites

- Python 3.13 or higher.
- A NextDNS account with API access.
- A NextDNS API key.

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/dbrennand/NextDNS-Rewrites.git
   cd NextDNS-Rewrites
   ```

2. Install dependencies using uv:

   ```bash
   uv sync
   ```

## Configuration

### Environment Variables

**Required:**
- `NEXTDNS_API_KEY`: Your NextDNS API key (get it from your NextDNS dashboard under *Settings*)

Set the environment variable:
```bash
export NEXTDNS_API_KEY="your-api-key-here"
```

### Configuration File

Create a `config.yaml` file with your NextDNS profile name and desired rewrites:

```yaml
# NextDNS Rewrites Configuration
profile_name: "Main"

rewrites:
  # A record example
  - name: "example.com"
    content: "1.1.1.1"
  # CNAME record example
  - name: "example.org"
    content: "example.com"
```

## Usage

Run the script with your configuration file:

```bash
uv run python main.py --config config.yaml
```

## How It Works

The script ensures all rewrites in your NextDNS profile match the desired state defined in your `config.yaml` file. For each rewrite in your configuration:

- **If the rewrite doesn't exist**: Creates a new rewrite.
- **If the rewrite exists**: Deletes the existing rewrite and creates a new one with the updated configuration. This approach is necessary because the NextDNS API doesn't provide PUT or PATCH methods for updating rewrites directly.

## Example Output

```
NextDNS Profile Name: Main
NextDNS profile found with name: Main and ID: abc123.
NextDNS rewrite example.com does not exist. Creating...
NextDNS rewrite example.com created with ID: def456.
NextDNS rewrite example.org already exists. Ensuring it is up to date.
NextDNS rewrite example.org deleted.
NextDNS rewrite example.org created with ID: ghi789.
```

## Development

### Code Quality

This project uses [Ruff](https://docs.astral.sh/ruff/) for code formatting and linting:

```bash
uv run ruff format main.py
```

## License

See [LICENSE](LICENSE) file for details.
