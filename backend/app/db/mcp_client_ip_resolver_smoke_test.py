from __future__ import annotations

from ipaddress import ip_address
from pathlib import Path

from app.core.client_ip import (
    ClientAddressError,
    TrustedProxyConfigurationError,
    TrustedProxyResolver,
    normalize_bind_address,
    normalize_trusted_proxy_cidrs,
)
from app.core.config import Settings


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def scope(
    peer: str,
    headers: list[tuple[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "type": "http",
        "client": (peer, 4242),
        "headers": [
            (name.encode("latin-1"), value.encode("latin-1"))
            for name, value in (headers or [])
        ],
    }


def expect_error(callable_value, exception_type, label: str) -> None:
    try:
        callable_value()
    except exception_type:
        return
    except Exception as exc:
        fail(f"{label} raised {type(exc).__name__}: {exc}")
    fail(f"{label} did not reject invalid input")


def check_configuration() -> None:
    if normalize_bind_address(" 127.0.0.1 ") != "127.0.0.1":
        fail("Bind address was not canonicalized")
    if normalize_bind_address("[2001:db8::1]") != "2001:db8::1":
        fail("IPv6 bind address was not canonicalized")
    expect_error(
        lambda: normalize_bind_address("localhost"),
        TrustedProxyConfigurationError,
        "Hostname bind address",
    )

    expected = ("10.0.0.1/32", "192.168.50.0/24", "2001:db8::/48")
    actual = normalize_trusted_proxy_cidrs(
        '["192.168.50.7/24", "10.0.0.1", "2001:db8::/48"]'
    )
    if actual != expected:
        fail(f"Trusted proxy CIDRs were not canonicalized: {actual}")
    expect_error(
        lambda: normalize_trusted_proxy_cidrs("0.0.0.0/0"),
        TrustedProxyConfigurationError,
        "Trust-all IPv4 proxy network",
    )
    expect_error(
        lambda: normalize_trusted_proxy_cidrs("10.0.0.0/8,10.1.0.0/16"),
        TrustedProxyConfigurationError,
        "Overlapping proxy networks",
    )
    expect_error(
        lambda: normalize_trusted_proxy_cidrs("not-a-network"),
        TrustedProxyConfigurationError,
        "Invalid proxy network",
    )

    settings = Settings.model_construct(
        bind_address="10.1.1.3",
        trusted_proxy_cidrs="172.19.0.11,2001:db8::/48",
    )
    if settings.normalized_bind_address != "10.1.1.3":
        fail("Settings bind-address property changed")
    if settings.trusted_proxy_cidr_list != (
        "172.19.0.11/32",
        "2001:db8::/48",
    ):
        fail("Settings trusted-proxy property changed")


def check_client_resolution() -> None:
    resolver = TrustedProxyResolver.from_raw(
        "10.0.0.0/8,192.168.50.10,2001:db8:1::/48"
    )
    direct = resolver.resolve_client_ip(
        scope(
            "203.0.113.9",
            [("X-Forwarded-For", "198.51.100.4")],
        )
    )
    if direct != ip_address("203.0.113.9"):
        fail("Untrusted peers were allowed to spoof X-Forwarded-For")

    single = resolver.resolve_client_ip(
        scope(
            "10.0.0.5",
            [("X-Forwarded-For", "198.51.100.4")],
        )
    )
    if single != ip_address("198.51.100.4"):
        fail("Trusted single-proxy resolution failed")

    chain = resolver.resolve_client_ip(
        scope(
            "10.0.0.5",
            [("X-Forwarded-For", "198.51.100.4, 192.168.50.10")],
        )
    )
    if chain != ip_address("198.51.100.4"):
        fail("Trusted multi-proxy resolution failed")

    ipv6 = resolver.resolve_client_ip(
        scope(
            "2001:db8:1::5",
            [("X-Forwarded-For", "2001:db8:ffff::8")],
        )
    )
    if ipv6 != ip_address("2001:db8:ffff::8"):
        fail("Trusted IPv6 proxy resolution failed")

    trusted_without_header = resolver.resolve_client_ip(scope("10.0.0.5"))
    if trusted_without_header != ip_address("10.0.0.5"):
        fail("Trusted peer without X-Forwarded-For changed")

    expect_error(
        lambda: resolver.resolve_client_ip(
            scope(
                "10.0.0.5",
                [
                    ("X-Forwarded-For", "198.51.100.4"),
                    ("x-forwarded-for", "198.51.100.5"),
                ],
            )
        ),
        ClientAddressError,
        "Duplicate X-Forwarded-For",
    )
    expect_error(
        lambda: resolver.resolve_client_ip(
            scope("10.0.0.5", [("X-Forwarded-For", "unknown")])
        ),
        ClientAddressError,
        "Malformed trusted X-Forwarded-For",
    )


def check_forwarded_origin() -> None:
    resolver = TrustedProxyResolver.from_raw("10.0.0.0/8")
    spoofed = resolver.forwarded_origin(
        scope(
            "203.0.113.9",
            [
                ("X-Forwarded-Proto", "https"),
                ("X-Forwarded-Host", "spoofed.example"),
            ],
        )
    )
    if spoofed is not None:
        fail("Untrusted forwarded origin was accepted")

    forwarded = resolver.forwarded_origin(
        scope(
            "10.0.0.5",
            [
                ("X-Forwarded-Proto", "https, http"),
                ("X-Forwarded-Host", "partpilot.example, internal:8000"),
            ],
        )
    )
    if (
        forwarded is None
        or forwarded.scheme != "https"
        or forwarded.host != "partpilot.example"
    ):
        fail(f"Trusted forwarded origin was not resolved: {forwarded}")

    expect_error(
        lambda: resolver.forwarded_origin(
            scope(
                "10.0.0.5",
                [("X-Forwarded-Proto", "javascript")],
            )
        ),
        ClientAddressError,
        "Invalid forwarded protocol",
    )
    expect_error(
        lambda: resolver.forwarded_origin(
            scope(
                "10.0.0.5",
                [
                    ("X-Forwarded-Host", "one.example"),
                    ("x-forwarded-host", "two.example"),
                ],
            )
        ),
        ClientAddressError,
        "Duplicate forwarded host",
    )


def check_deployment_contract() -> None:
    dockerfile = Path("/app/backend/Dockerfile")
    if dockerfile.exists():
        content = dockerfile.read_text(encoding="utf-8")
        if "--no-proxy-headers" not in content:
            fail("Production Uvicorn command does not disable implicit proxy rewriting")


def main() -> None:
    check_configuration()
    check_client_resolution()
    check_forwarded_origin()
    check_deployment_contract()
    print(
        "[PASS] Explicit MCP proxy configuration canonicalizes bind/CIDR values, "
        "rejects trust-all and overlapping networks, ignores spoofed forwarding from "
        "untrusted peers, resolves trusted IPv4/IPv6 proxy chains, rejects ambiguous "
        "headers, and provides trusted forwarded-origin metadata without enabling "
        "trusted-network authentication"
    )


# PARTPILOT:MCP_CLIENT_IP_RESOLVER_SMOKE:V506
if __name__ == "__main__":
    main()
