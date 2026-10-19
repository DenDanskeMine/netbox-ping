"""Unit tests for netbox_ping/compat.py.

NetBox 4.7 changed the list view `actions` attribute from a dict to an iterable
of ObjectAction classes, so the plugin has to pick the right form at import time.
"""

import importlib
import sys
from types import ModuleType

import pytest


@pytest.fixture
def reload_compat():
    saved = sys.modules.pop("netbox.object_actions", None)

    def _reload():
        import netbox_ping.compat as compat

        return importlib.reload(compat)

    yield _reload

    sys.modules.pop("netbox.object_actions", None)
    if saved is not None:
        sys.modules["netbox.object_actions"] = saved
    _reload()


def test_uses_object_action_classes_on_netbox_4_7(reload_compat):
    module = ModuleType("netbox.object_actions")
    module.BulkExport = type("BulkExport", (), {})
    module.BulkDelete = type("BulkDelete", (), {})
    sys.modules["netbox.object_actions"] = module

    compat = reload_compat()

    assert compat.LIST_VIEW_ACTIONS == (module.BulkExport, module.BulkDelete)


def test_falls_back_to_dict_before_netbox_4_7(reload_compat):
    compat = reload_compat()

    assert compat.LIST_VIEW_ACTIONS == {
        "export": set(),
        "bulk_delete": {"delete"},
    }
