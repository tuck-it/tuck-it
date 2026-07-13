import pytest


@pytest.mark.django_db
def test_login_screen_uses_design_system(client, workspace):
    body = client.get("/login/").content.decode()
    # standalone page, English, not the app shell
    assert '<html lang="en"' in body
    assert 'class="auth-card"' in body
    # token chain linked in order, ending in auth.css; app.css NOT linked
    i_brand = body.find("tokens.brand.css")
    i_product = body.find("tokens.product.css")
    i_base = body.find("web/base.css")
    i_auth = body.find("web/auth.css")
    assert -1 not in (i_brand, i_product, i_base, i_auth)
    assert i_brand < i_product < i_base < i_auth
    assert "web/app.css" not in body
    # login form fields preserved (names unchanged)
    assert 'name="username"' in body
    assert 'name="password"' in body
