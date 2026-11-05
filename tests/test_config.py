import pytest
import yaml

from ndrw.config import ConfigError, load_config


def write_config(tmp_path, data):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


@pytest.mark.parametrize(
    "name,content",
    [
        ("example.com", "1.1.1.1"),
        ("*.example.com", "2001:db8::1"),
        ("Example.com.", "target.example.org."),
        ("localhost", "127.0.0.1"),
    ],
)
def test_valid_rewrite(tmp_path, name, content):
    rewrite = {"name": name, "content": content}
    config = load_config(
        write_config(tmp_path, {"profile": "Main", "rewrites": [rewrite]})
    )
    assert config.profile == "Main"
    assert config.rewrites == [rewrite]


def test_explicit_empty_list_is_valid(tmp_path):
    assert (
        load_config(
            write_config(tmp_path, {"profile": "Main", "rewrites": []})
        ).rewrites
        == []
    )


@pytest.mark.parametrize(
    "data,message",
    [
        (None, "YAML mapping"),
        ([], "YAML mapping"),
        ({}, "profile"),
        ({"profile_name": "Main"}, "Rename 'profile_name'"),
        ({"profile": "Main", "rewrite": []}, "Unknown configuration fields"),
        ({"profile": " "}, "non-empty profile name"),
        ({"profile": 123}, "non-empty profile name"),
        ({"profile": "Main"}, "explicit list"),
        ({"profile": "Main", "rewrites": None}, "explicit list"),
        ({"profile": "Main", "rewrites": {}}, "explicit list"),
    ],
)
def test_invalid_config(tmp_path, data, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, data))


@pytest.mark.parametrize(
    "rewrite,message",
    [
        (None, "exactly 'name' and 'content'"),
        ({"name": "example.com"}, "exactly 'name' and 'content'"),
        (
            {"name": "example.com", "content": "1.1.1.1", "extra": True},
            "exactly 'name' and 'content'",
        ),
        ({"name": "", "content": "1.1.1.1"}, "non-empty string"),
        ({"name": "example.com", "content": 123}, "non-empty string"),
        ({"name": " example.com", "content": "1.1.1.1"}, "surrounding whitespace"),
        ({"name": "example.com", "content": " "}, "non-empty string"),
        ({"name": "bad..com", "content": "1.1.1.1"}, "valid DNS hostname"),
        ({"name": "-bad.com", "content": "1.1.1.1"}, "valid DNS hostname"),
        ({"name": "a" * 254, "content": "1.1.1.1"}, "valid DNS hostname"),
        ({"name": "example.com", "content": "999.1.1.1"}, "IPv4 address"),
        ({"name": "example.com", "content": "bad:ipv6"}, "IPv4 address"),
        ({"name": "example.com", "content": "https://example.com"}, "IPv4 address"),
    ],
)
def test_malformed_rewrite(tmp_path, rewrite, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, {"profile": "Main", "rewrites": [rewrite]}))


def test_duplicate_names_are_case_and_trailing_dot_insensitive(tmp_path):
    data = {
        "profile": "Main",
        "rewrites": [
            {"name": "Example.com.", "content": "1.1.1.1"},
            {"name": "example.com", "content": "2.2.2.2"},
        ],
    }
    with pytest.raises(ConfigError, match="Duplicate rewrite name"):
        load_config(write_config(tmp_path, data))


@pytest.mark.parametrize(
    "text,message",
    [
        ("", "YAML mapping"),
        ("profile: [", "Cannot load configuration"),
        ("profile: Main\nprofile: Other\nrewrites: []", "Duplicate YAML key"),
        (
            "profile: Main\nrewrites:\n  - name: a.com\n    name: b.com\n    content: 1.1.1.1",
            "Duplicate YAML key",
        ),
        ("123: value", "keys must be strings"),
    ],
)
def test_invalid_yaml(tmp_path, text, message):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    with pytest.raises(ConfigError, match=message):
        load_config(path)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="Cannot load configuration"):
        load_config(tmp_path / "missing.yaml")
