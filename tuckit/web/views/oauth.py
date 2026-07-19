from django.conf import settings
from django.http import JsonResponse


def issuer(request) -> str:
    if settings.TUCKIT_OAUTH_ISSUER:
        return settings.TUCKIT_OAUTH_ISSUER.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def protected_resource_metadata(request):
    """RFC 9728 Protected Resource Metadata for the /mcp resource."""
    iss = issuer(request)
    return JsonResponse({
        "resource": f"{iss}/mcp",
        "authorization_servers": [iss],
        "bearer_methods_supported": ["header"],
    })


def authorization_server_metadata(request):
    """RFC 8414 Authorization Server Metadata."""
    iss = issuer(request)
    return JsonResponse({
        "issuer": iss,
        "authorization_endpoint": f"{iss}/oauth/authorize",
        "token_endpoint": f"{iss}/oauth/token",
        "registration_endpoint": f"{iss}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    })
