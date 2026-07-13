import pytest


@pytest.mark.django_db
def test_custom_user_model_is_active():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert User.__name__ == "User"
    assert User._meta.app_label == "core"
    u = User.objects.create_user(email="alice@x.com", password="x")
    assert u.pk is not None
