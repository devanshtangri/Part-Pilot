from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Iterator

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


ORIGIN_METADATA = "/.well-known/oauth-authorization-server"
RESOURCE_METADATA = "/.well-known/oauth-protected-resource/mcp"


class PeerOverride:
    def __init__(self, target) -> None:
        self.target = target
        self.peer = "198.51.100.25"

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http":
            scope = dict(scope)
            scope["client"] = (self.peer, 43125)
        await self.target(scope, receive, send)


def fail(message: str) -> None:
    raise RuntimeError(message)


@contextmanager
def settings_environment(
    *,
    public_base_url: str = "",
    trusted_proxy_cidrs: str = "",
) -> Iterator[None]:
    values = {
        "PARTPILOT_PUBLIC_BASE_URL": public_base_url,
        "PARTPILOT_TRUSTED_PROXY_CIDRS": trusted_proxy_cidrs,
    }
    original = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        get_settings.cache_clear()
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def metadata_origin(response, label: str) -> str:
    if response.status_code != 200:
        fail(f"{label} returned {response.status_code}: {response.text}")
    issuer = response.json().get("issuer")
    if not isinstance(issuer, str):
        fail(f"{label} omitted issuer: {response.json()}")
    return issuer


def challenge_origin(response, label: str) -> str:
    if response.status_code != 401:
        fail(f"{label} returned {response.status_code}: {response.text}")
    challenge = response.headers.get("www-authenticate", "")
    marker = 'resource_metadata="'
    if marker not in challenge:
        fail(f"{label} omitted resource metadata: {challenge!r}")
    return challenge.split(marker, 1)[1].split('"', 1)[0]


def check_untrusted_forwarding_is_ignored(
    client: TestClient,
    peer: PeerOverride,
) -> None:
    peer.peer = "198.51.100.25"
    with settings_environment():
        headers = {
            "Host": "internal:8000",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Host": "spoofed.example",
        }
        issuer = metadata_origin(
            client.get(ORIGIN_METADATA, headers=headers),
            "Untrusted OAuth forwarding",
        )
        if issuer != "https://internal:8000":
            fail(f"Untrusted forwarding changed OAuth origin: {issuer}")
        challenge = challenge_origin(
            client.post("/mcp", headers=headers, json={}),
            "Untrusted MCP forwarding",
        )
        expected = "https://internal:8000/.well-known/oauth-protected-resource/mcp"
        if challenge != expected:
            fail(f"Untrusted forwarding changed MCP challenge: {challenge}")

        duplicate = client.get(
            ORIGIN_METADATA,
            headers=[
                ("Host", "internal:8000"),
                ("X-Forwarded-Host", "one.example"),
                ("X-Forwarded-Host", "two.example"),
                ("X-Forwarded-Proto", "javascript"),
            ],
        )
        if duplicate.status_code != 200:
            fail(
                "Malformed forwarding from an untrusted peer was not ignored: "
                f"{duplicate.status_code} {duplicate.text}"
            )


def check_trusted_forwarding_is_used(
    client: TestClient,
    peer: PeerOverride,
) -> None:
    peer.peer = "10.0.0.5"
    with settings_environment(trusted_proxy_cidrs="10.0.0.0/24"):
        headers = {
            "Host": "internal:8000",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "partpilot.example",
        }
        issuer = metadata_origin(
            client.get(ORIGIN_METADATA, headers=headers),
            "Trusted OAuth forwarding",
        )
        if issuer != "https://partpilot.example":
            fail(f"Trusted forwarding did not set OAuth origin: {issuer}")
        challenge = challenge_origin(
            client.post("/mcp", headers=headers, json={}),
            "Trusted MCP forwarding",
        )
        expected = "https://partpilot.example/.well-known/oauth-protected-resource/mcp"
        if challenge != expected:
            fail(f"Trusted forwarding did not set MCP challenge: {challenge}")

        invalid_headers = {
            "Host": "internal:8000",
            "X-Forwarded-Proto": "javascript",
            "X-Forwarded-Host": "partpilot.example",
        }
        invalid_oauth = client.get(ORIGIN_METADATA, headers=invalid_headers)
        if invalid_oauth.status_code != 400:
            fail(
                "Invalid trusted OAuth forwarding was not rejected: "
                f"{invalid_oauth.status_code} {invalid_oauth.text}"
            )
        invalid_mcp = client.post("/mcp", headers=invalid_headers, json={})
        if invalid_mcp.status_code != 400:
            fail(
                "Invalid trusted MCP forwarding was not rejected: "
                f"{invalid_mcp.status_code} {invalid_mcp.text}"
            )


def check_explicit_public_origin_wins(
    client: TestClient,
    peer: PeerOverride,
) -> None:
    peer.peer = "198.51.100.25"
    with settings_environment(public_base_url="https://part.devansh.cc/"):
        spoofed = {
            "Host": "internal:8000",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Host": "spoofed.example",
        }
        issuer = metadata_origin(
            client.get(ORIGIN_METADATA, headers=spoofed),
            "Configured OAuth origin",
        )
        if issuer != "https://part.devansh.cc":
            fail(f"Configured public origin was not canonicalized: {issuer}")
        resource = client.get(RESOURCE_METADATA, headers=spoofed)
        if resource.status_code != 200 or resource.json().get("resource") != (
            "https://part.devansh.cc/mcp"
        ):
            fail(f"Configured resource metadata is wrong: {resource.text}")
        challenge = challenge_origin(
            client.post("/mcp", headers=spoofed, json={}),
            "Configured MCP origin",
        )
        expected = "https://part.devansh.cc/.well-known/oauth-protected-resource/mcp"
        if challenge != expected:
            fail(f"Configured public origin did not set MCP challenge: {challenge}")


def main() -> int:
    peer = PeerOverride(app)
    with TestClient(peer, base_url="https://internal:8000") as client:
        check_untrusted_forwarding_is_ignored(client, peer)
        check_trusted_forwarding_is_used(client, peer)
        check_explicit_public_origin_wins(client, peer)
    print(
        "[PASS] MCP and OAuth use only configured or explicitly trusted forwarded "
        "origins, ignore spoofed forwarding from untrusted peers, reject malformed "
        "trusted forwarding, preserve protected-resource challenges, and do not "
        "enable trusted-network authentication"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# PARTPILOT:MCP_FORWARDED_ORIGIN_RUNTIME_SMOKE:V508
