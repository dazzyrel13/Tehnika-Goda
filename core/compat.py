"""Runtime shims for known Django / Python incompatibilities."""

from __future__ import annotations

import sys


def patch_django_template_context_copy() -> None:
    """
    Django 5.1 BaseContext.__copy__ uses copy(super()), which breaks on Python 3.14+.
    Replace with a plain instance clone so TestCase template rendering works.
    """
    if sys.version_info < (3, 14):
        return

    from django.template import context as template_context

    def _safe_base_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    template_context.BaseContext.__copy__ = _safe_base_copy  # type: ignore[method-assign]
