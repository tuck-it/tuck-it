"""Django admin registrations for the core models.

Split by domain to mirror ``tuckit.core.models``. Importing this package
(Django's admin autodiscover imports ``tuckit.core.admin``) registers every
core model so local development has full DB visibility at ``/admin/``.
"""

from tuckit.core.admin import accounts, activity, domain, org, workspace  # noqa: F401
