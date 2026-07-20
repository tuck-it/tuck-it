import logging

from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from tuckit.core.services.social import PROVIDERS, SocialLoginError, resolve_social_login
from tuckit.core.services.social.oauth_client import begin_url, exchange_and_fetch
from tuckit.web.views.accounts import _safe_next, _success

log = logging.getLogger(__name__)
SESSION_KEY = "social_oauth"


def _enabled(request, provider_name):
    from django.conf import settings

    cfg = getattr(settings, "SOCIAL_PROVIDERS", {}).get(provider_name)
    provider = PROVIDERS.get(provider_name)
    if not cfg or provider is None:
        raise Http404("Unknown or disabled provider.")
    return provider, cfg


def _redirect_uri(request, provider_name):
    return request.build_absolute_uri(reverse("web:social_callback", args=[provider_name]))


def _login_error(request, message):
    """Re-render the login email step with an error (mirrors accounts._render)."""
    return render(request, "registration/login.html", {"step": "email", "next": "", "error": message})


def social_begin(request, provider):
    prov, cfg = _enabled(request, provider)
    url, state, code_verifier = begin_url(prov, cfg, _redirect_uri(request, provider))
    request.session[SESSION_KEY] = {
        "provider": provider,
        "state": state,
        "code_verifier": code_verifier,
        "next": _safe_next(request),
    }
    return redirect(url)


def social_callback(request, provider):
    prov, cfg = _enabled(request, provider)
    stashed = request.session.pop(SESSION_KEY, None)

    if request.GET.get("error") or not stashed or stashed.get("provider") != provider:
        return _login_error(request, "Sign-in was cancelled or failed. Please try again.")
    if not request.GET.get("state") or request.GET["state"] != stashed.get("state"):
        return _login_error(request, "Sign-in could not be verified. Please try again.")

    try:
        identity = exchange_and_fetch(
            prov, cfg, _redirect_uri(request, provider),
            stashed["state"], stashed["code_verifier"],
            request.build_absolute_uri(),
        )
    except Exception:
        log.exception("social token exchange/userinfo failed for provider=%s", provider)
        return _login_error(request, "We couldn't complete sign-in. Please try again.")

    try:
        user = resolve_social_login(
            provider=provider, uid=identity.uid, email=identity.email,
            email_verified=identity.email_verified, name=identity.name,
        )
    except SocialLoginError as exc:
        return _login_error(request, str(exc))

    login(request, user)
    # Reuse the email flow's post-login redirect, honoring the stashed `next`.
    if stashed.get("next"):
        return redirect(stashed["next"])
    return _success(request)
