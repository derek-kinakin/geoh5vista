"""Workarounds for geoh5py reader limitations."""

from __future__ import annotations

import warnings
from functools import wraps

from geoh5py.io.h5_reader import H5Reader
from geoh5py.shared import fetch_h5_handle
from geoh5py.shared.utils import KEY_MAP, PROPERTY_KWARGS, as_str_if_uuid

_PATCH_FLAG = "_geoh5vista_missing_concatenated_data"


def _index_without_data(h5file, uid, entity_type: str, label: str) -> bool:
    """Return True when a concatenated field has an ``Index`` entry but no stored array."""
    if label in PROPERTY_KWARGS:
        label = KEY_MAP.get(label, label)
    key = label.replace("/", "\u2044")
    try:
        group = h5file[next(iter(h5file))][H5Reader.format_type_string(entity_type)][as_str_if_uuid(uid)][
            "Concatenated Data"
        ]
    except KeyError:
        return False
    index = group.get("Index")
    if index is None or key not in index:
        return False
    data = group.get("Data")
    return not ((data is not None and key in data) or key in group)


def patch_missing_concatenated_data() -> None:
    """Let geoh5py read concatenated groups whose ``Index`` lists fields with no data array.

    Some writers (e.g. drillhole groups without surveys) leave entries such as
    ``Property Group IDs``, ``Trace`` or ``TraceDepth`` in ``Concatenated Data/Index``
    without the matching array. geoh5py 0.13 then fails with
    ``TypeError: 'NoneType' object is not subscriptable`` while opening the workspace.
    The patched reader treats such fields as absent, which is how geoh5py already handles
    a field with no index entry. Well-formed files are unaffected. Safe to call repeatedly.
    """
    original = H5Reader.fetch_concatenated_values
    if getattr(original, _PATCH_FLAG, False):
        return

    @wraps(original)
    def fetch_concatenated_values(file, uid, entity_type, label):
        with fetch_h5_handle(file) as h5file:
            missing = _index_without_data(h5file, uid, entity_type, label)
        if missing:
            warnings.warn(
                f"Concatenated field '{label}' of {entity_type} {as_str_if_uuid(uid)} is indexed "
                "but has no stored data; ignoring it.",
                stacklevel=2,
            )
            return None
        return original(file, uid, entity_type, label)

    setattr(fetch_concatenated_values, _PATCH_FLAG, True)
    H5Reader.fetch_concatenated_values = staticmethod(fetch_concatenated_values)
