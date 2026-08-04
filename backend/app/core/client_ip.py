from __future__ import annotations

from dataclasses import dataclass
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
import json
from typing import Any


IpAddress = IPv4Address | IPv6Address
IpNetwork = IPv4Network | IPv6Network
MAX_TRUSTED_PROXY_NETWORKS = 64
MAX_FORWARDED_HOPS = 32


class TrustedProxyConfigurationError(ValueError):
    pass


class ClientAddressError(ValueError):
    pass


def _parse_ip(value: object, *, label: str) -> IpAddress:
    if not isinstance(value, str):
        raise ClientAddressError(f"{label} must be an IP address.")
    candidate = value.strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    if not candidate or "%" in candidate:
        raise ClientAddressError(f"{label} must be an unscoped IP address.")
    try:
        return ip_address(candidate)
    except ValueError as exc:
        raise ClientAddressError(f"{label} must be an IP address.") from exc


def normalize_bind_address(raw: str) -> str:
    try:
        return str(_parse_ip(raw, label="PARTPILOT_BIND_ADDRESS"))
    except ClientAddressError as exc:
        raise TrustedProxyConfigurationError(str(exc)) from exc


def _configured_items(raw: str | None) -> list[str]:
    value = (raw or "").strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise TrustedProxyConfigurationError(
                "PARTPILOT_TRUSTED_PROXY_CIDRS must be comma-separated CIDRs or a JSON list."
            ) from exc
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise TrustedProxyConfigurationError(
                "PARTPILOT_TRUSTED_PROXY_CIDRS JSON must contain only strings."
            )
        return [item.strip() for item in parsed if item.strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_trusted_proxy_cidrs(raw: str | None) -> tuple[str, ...]:
    items = _configured_items(raw)
    if len(items) > MAX_TRUSTED_PROXY_NETWORKS:
        raise TrustedProxyConfigurationError(
            f"At most {MAX_TRUSTED_PROXY_NETWORKS} trusted proxy networks are allowed."
        )
    networks: list[IpNetwork] = []
    for item in items:
        try:
            network = ip_network(item, strict=False)
        except ValueError as exc:
            raise TrustedProxyConfigurationError(
                f"Invalid trusted proxy network: {item!r}."
            ) from exc
        if network.prefixlen == 0:
            raise TrustedProxyConfigurationError(
                "Trust-all proxy networks are not allowed."
            )
        for existing in networks:
            if network.version == existing.version and network.overlaps(existing):
                raise TrustedProxyConfigurationError(
                    f"Trusted proxy networks overlap: {existing} and {network}."
                )
        networks.append(network)
    networks.sort(
        key=lambda network: (
            network.version,
            int(network.network_address),
            network.prefixlen,
        )
    )
    return tuple(str(network) for network in networks)


def _header_values(scope: dict[str, Any], name: str) -> list[str]:
    target = name.casefold()
    values: list[str] = []
    for raw_name, raw_value in scope.get("headers", ()):
        try:
            header_name = raw_name.decode("latin-1").casefold()
            header_value = raw_value.decode("latin-1")
        except (AttributeError, UnicodeDecodeError):
            continue
        if header_name == target:
            values.append(header_value)
    return values


def _single_header(scope: dict[str, Any], name: str) -> str | None:
    values = _header_values(scope, name)
    if len(values) > 1:
        raise ClientAddressError(f"Duplicate {name} headers are not allowed.")
    return values[0] if values else None


def _forwarded_items(value: str, *, label: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    if not items or any(not item for item in items):
        raise ClientAddressError(f"{label} contains an empty value.")
    if len(items) > MAX_FORWARDED_HOPS:
        raise ClientAddressError(
            f"{label} exceeds the {MAX_FORWARDED_HOPS}-hop limit."
        )
    return items


@dataclass(frozen=True)
class TrustedForwardedOrigin:
    scheme: str | None
    host: str | None


@dataclass(frozen=True)
class TrustedProxyResolver:
    networks: tuple[IpNetwork, ...]

    @classmethod
    def from_raw(cls, raw: str | None) -> "TrustedProxyResolver":
        return cls(
            tuple(
                ip_network(value, strict=True)
                for value in normalize_trusted_proxy_cidrs(raw)
            )
        )

    def peer_ip(self, scope: dict[str, Any]) -> IpAddress:
        client = scope.get("client")
        if not isinstance(client, (tuple, list)) or len(client) != 2:
            raise ClientAddressError("ASGI client address is missing.")
        return _parse_ip(client[0], label="ASGI client address")

    def is_trusted(self, address: IpAddress) -> bool:
        return any(
            address.version == network.version and address in network
            for network in self.networks
        )

    def immediate_peer_is_trusted(self, scope: dict[str, Any]) -> bool:
        if not self.networks:
            return False
        return self.is_trusted(self.peer_ip(scope))

    def resolve_client_ip(self, scope: dict[str, Any]) -> IpAddress:
        peer = self.peer_ip(scope)
        if not self.is_trusted(peer):
            return peer
        forwarded = _single_header(scope, "x-forwarded-for")
        if forwarded is None:
            return peer
        addresses = [
            _parse_ip(item, label="X-Forwarded-For value")
            for item in _forwarded_items(
                forwarded,
                label="X-Forwarded-For",
            )
        ]
        candidate = peer
        for address in reversed(addresses):
            if not self.is_trusted(candidate):
                break
            candidate = address
        return candidate

    def forwarded_origin(
        self,
        scope: dict[str, Any],
    ) -> TrustedForwardedOrigin | None:
        if not self.immediate_peer_is_trusted(scope):
            return None
        raw_scheme = _single_header(scope, "x-forwarded-proto")
        raw_host = _single_header(scope, "x-forwarded-host")
        if raw_scheme is None and raw_host is None:
            return None
        scheme: str | None = None
        host: str | None = None
        if raw_scheme is not None:
            schemes = [
                item.casefold()
                for item in _forwarded_items(
                    raw_scheme,
                    label="X-Forwarded-Proto",
                )
            ]
            if any(item not in {"http", "https"} for item in schemes):
                raise ClientAddressError(
                    "X-Forwarded-Proto must contain only http or https."
                )
            scheme = schemes[0]
        if raw_host is not None:
            hosts = _forwarded_items(
                raw_host,
                label="X-Forwarded-Host",
            )
            if any(
                any(character in item for character in "\\/\r\n\t #?")
                for item in hosts
            ):
                raise ClientAddressError("X-Forwarded-Host is invalid.")
            host = hosts[0]
        return TrustedForwardedOrigin(scheme=scheme, host=host)


# PARTPILOT:MCP_TRUSTED_PROXY_RESOLVER:V506
