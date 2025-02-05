# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Helpers for driving relation databag operations using pydantic models."""

import json
import logging
from typing import MutableMapping, Optional, Type

import pydantic

# Note: MutableMapping is imported from the typing module and not collections.abc
# because subscripting collections.abc.MutableMapping was added in python 3.9, but
# most of our charms are based on 20.04, which has python 3.8.
_RawDatabag = MutableMapping[str, str]


log = logging.getLogger(__name__)


# Adapted from https://github.com/canonical/cos-lib/blob/main/src/cosl/interfaces/utils.py's DatabagModelV2
def load_from_databag(model: Type[pydantic.BaseModel], databag: Optional[_RawDatabag]) -> pydantic.BaseModel:
    """Load a pydantic model from a Juju databag."""
    try:
        return model.model_validate_json(json.dumps(dict(databag)))  # type: ignore
    except pydantic.ValidationError as e:
        msg = f"failed to validate databag: {databag}"
        if databag:
            log.debug(msg, exc_info=True)
        raise e

def dump_to_databag(data: pydantic.BaseModel, databag: Optional[_RawDatabag] = None, clear: bool = True) -> _RawDatabag:
    """Write the contents of a pydantic model to a Juju databag.

    :param data: the data model instance to write the data from.
    :param databag: the databag to write the data to.
    :param clear: ensure the databag is cleared before writing it.
    """
    _databag: _RawDatabag = {} if databag is None else databag

    if clear:
        _databag.clear()

    dct = data.model_dump(mode="json", by_alias=True, exclude_defaults=True, round_trip=True)  # type: ignore
    _databag.update(dct)
    return _databag
