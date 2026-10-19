"""Helpers for supporting more than one NetBox release."""

try:
    # NetBox 4.7+ expects `actions` to be an iterable of ObjectAction classes
    from netbox.object_actions import BulkDelete, BulkExport

    LIST_VIEW_ACTIONS = (BulkExport, BulkDelete)
except ImportError:
    # NetBox 4.5 and 4.6 expect a dict of {action name: required permissions}
    LIST_VIEW_ACTIONS = {
        'export': set(),
        'bulk_delete': {'delete'},
    }
