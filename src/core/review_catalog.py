"""Deterministic MCP tool catalogs for public clients and review profiles.

Public list_tools stays the ordinary MCP surface. Review capabilities see the
versioned Tool API catalogs; Web Server remains the authorization boundary.
"""

from __future__ import annotations

from fastmcp.server.auth import AccessToken

REVIEWER_PROFILE_VERSION = "reviewer-tools:v1"
SYNTHESIZER_PROFILE_VERSION = "synthesizer-tools:v1"

# Ordinary MCP clients. ask_codebase is registered but not advertised here.
PUBLIC_TOOL_NAMES: tuple[str, ...] = (
    "get_data_sources",
    "semantic_search",
    "grep_search",
    "get_repository_ontology",
    "get_file_tree",
    "read_file",
    "fetch_artifacts",
    "get_artifact_relationships",
    "get_artifact_query_schema",
    "query_artifact_metadata",
    "chat",
)

# Provider-facing review catalogs. Order is part of the contract.
REVIEWER_TOOL_NAMES: tuple[str, ...] = (
    "ask_codebase",
    "get_data_sources",
    "semantic_search",
    "grep_search",
    "get_file_tree",
    "read_file",
    "fetch_artifacts",
    "get_artifact_relationships",
    "get_artifact_query_schema",
    "query_artifact_metadata",
)

SYNTHESIZER_TOOL_NAMES: tuple[str, ...] = (
    *REVIEWER_TOOL_NAMES,
    "get_repository_ontology",
)


def exact_audience(claims: dict[str, object], expected: str) -> bool:
    """Require a single string audience. Lists and extras fail closed."""
    return claims.get("aud") == expected


def is_verified_review_capability(
    access: AccessToken | None,
    tool_api_resource: str,
) -> bool:
    """True only after issuer/JWKS verification bound the Tool API audience."""
    if access is None:
        return False
    claims = access.claims or {}
    return exact_audience(claims, tool_api_resource)


def advertised_tool_names(
    access: AccessToken | None,
    *,
    tool_api_resource: str,
) -> tuple[str, ...]:
    """Return the catalog the current credential may see.

    PUBLIC is only for non-review credentials. A verified Tool API review
    capability sees its closed v1 list, or an empty catalog when the profile
    is missing or unknown. No wildcard future grants.
    """
    if not is_verified_review_capability(access, tool_api_resource):
        return PUBLIC_TOOL_NAMES
    claims = access.claims or {}
    profile = claims.get("review_tool_profile")
    if profile == REVIEWER_PROFILE_VERSION:
        return REVIEWER_TOOL_NAMES
    if profile == SYNTHESIZER_PROFILE_VERSION:
        return SYNTHESIZER_TOOL_NAMES
    return ()
