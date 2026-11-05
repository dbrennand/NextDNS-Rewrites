# ndrw

Manage NextDNS rewrites from a YAML configuration using the `ndrw` CLI.

## Requirements

- Python 3.15 or higher
- A [NextDNS](https://nextdns.io/) account
- A NextDNS API key (see [Get a NextDNS API key](#get-a-nextdns-api-key))

## Get a NextDNS API key

Open the [NextDNS account page](https://my.nextdns.io/account), then copy the API
key shown in the **API** section. The CLI reads this key from the
`NEXTDNS_API_KEY` environment variable.

Treat the key as a secret: do not put it in `config.yaml` or commit it to source
control.

## Installation

Install the CLI directly from the repository with
[uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/dbrennand/NextDNS-Rewrites.git
```

This installs the `ndrw` command.

## Quick start

1. Export your NextDNS API key:

   ```bash
   export NEXTDNS_API_KEY="your-api-key-here"
   ```

2. Create `config.yaml`, using the name of the NextDNS profile you want to
   manage:

   ```yaml
   profile: "Main"
   rewrites:
     - name: "example.com"
       content: "1.1.1.1"
     - name: "ipv6.example.com"
       content: "2001:db8::1"
   ```

3. Apply the rewrites:

   ```bash
   ndrw --config config.yaml
   ```

Existing remote rewrites with configured names are deleted and recreated on
every run, even when their content is unchanged. Remote rewrites whose names are
not in the configuration are preserved unless `--prune` is supplied.

## CLI options

```text
ndrw --config PATH [--dry-run] [--prune]
ndrw --help
ndrw --version
```

- `--config PATH` (required): path to the YAML configuration file.
- `--dry-run`: read the profile and its rewrites from NextDNS and report the
  planned creates, replacements, and deletions without changing anything. An API
  key and network access are still required.
- `--prune`: delete remote rewrites whose names are absent from the
  configuration. Preview these deletions with `--dry-run` before applying them.
- `--help`: show the command help and exit.
- `--version`: show the installed `ndrw` version and exit.

For example, preview and then apply a configuration that removes unconfigured
remote rewrites:

```bash
ndrw --config config.yaml --prune --dry-run
ndrw --config config.yaml --prune
```

Successful runs exit with status `0`. Configuration, authentication, network,
and NextDNS API errors exit with status `1`; invalid command-line arguments exit
with status `2`.

## Configuration reference

The configuration file is a YAML mapping with exactly two top-level fields:

```yaml
profile: "Main"
rewrites:
  - name: "example.com"
    content: "1.1.1.1"
  - name: "service.example.com"
    content: "target.example.net"
  - name: "*.internal.example.com"
    content: "2001:db8::1"
```

### `profile`

`profile` is required and must be a non-empty string containing the exact name
of one NextDNS profile. After validating the file locally, `ndrw` looks up the
profile through the API and requires exactly one match.

### `rewrites`

`rewrites` is required and must be a list. Each item must contain exactly these
two fields:

- `name`: a non-empty ASCII DNS hostname, optionally beginning with `*.`.
  Internationalized names must use punycode.
- `content`: a non-empty IPv4 address, IPv6 address, or DNS hostname. A hostname
  represents a CNAME-style rewrite.

Values cannot have surrounding whitespace. Rewrite names must be unique,
ignoring case and an optional trailing dot. Duplicate YAML keys, unknown fields,
malformed YAML, empty files, and invalid values are rejected before NextDNS is
contacted.

An explicit empty list is valid:

```yaml
profile: "Main"
rewrites: []
```

Without `--prune`, this makes no changes. With `--prune`, it deletes every
rewrite in the selected profile. Omitting `rewrites` is always an error.

### Apply behavior

Configured rewrites are processed in file order. A missing rewrite is created.
Every existing remote rewrite with the same normalized name is deleted, then one
configured rewrite is created. When `--prune` is enabled, unconfigured remote
rewrites are deleted after configured rewrites have been applied.

Operations are sequential and are not rolled back. If an API operation fails,
processing stops immediately; changes already made remain in place. In
particular, if creation fails after an existing rewrite was deleted, that rewrite
remains absent.

The original project's testing found that hostname content did not resolve as
expected; see the
[NextDNS discussion](https://help.nextdns.io/t/p8yx4pk?r=p8y1ct8).

## Development

```bash
uv sync --locked --group test
uv run --locked ruff format .
uv run --locked ruff check .
uv run --locked --group test pytest
uv build
```

Ruff is in the `dev` dependency group; pytest and pytest-cov are in the separate
`test` group, enabled with `--group test`. Ruff enforces Google-style docstrings
in source code. Tests are excluded from docstring checks and remain subject to
linting and formatting.

Tests mock all NextDNS operations and never change real profiles. Running pytest
measures line and branch coverage for the `ndrw` package, prints missing lines,
writes `coverage.xml`, and fails below **80% total coverage**. Generate a browsable
report with `uv run --group test pytest --cov-report=html` and open
`htmlcov/index.html`.

GitHub Actions runs linting, formatting, tests with the coverage threshold, a
package build, and an installed CLI smoke check on Python 3.15. Third-party
actions are pinned to full commit SHAs; uv is pinned to a specific release. The
workflow uses read-only repository permissions and does not require a NextDNS
API key.

## License

See [LICENSE](LICENSE).
