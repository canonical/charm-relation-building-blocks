# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Pydantic model for Juju databags."""

import json
import logging
from typing import MutableMapping, Optional

import pydantic

# Note: MutableMapping is imported from the typing module and not collections.abc
# because subscripting collections.abc.MutableMapping was added in python 3.9, but
# most of our charms are based on 20.04, which has python 3.8.
_RawDatabag = MutableMapping[str, str]


log = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when relation databag validation fails."""


class DatabagModel(pydantic.BaseModel):
    """Base databag model."""

    # This is vendored from https://github.com/canonical/cos-lib/blob/main/src/cosl/interfaces/utils.py's DatabagModelV2
    # to avoid a dependency on cos-lib
    model_config = pydantic.ConfigDict(
        # tolerate additional keys in databag
        extra="ignore",
        # Allow instantiating this class by field name (instead of forcing alias).
        populate_by_name=True,
    )  # type: ignore
    """Pydantic config."""

    @classmethod
    def load(cls, databag: _RawDatabag):
        """Load this model from a Juju databag."""
        try:
            return cls.model_validate_json(json.dumps(dict(databag)))  # type: ignore
        except pydantic.ValidationError as e:
            msg = f"failed to validate databag: {databag}"
            if databag:
                log.debug(msg, exc_info=True)
            raise DataValidationError(msg) from e

    def dump(self, databag: Optional[_RawDatabag] = None, clear: bool = True) -> _RawDatabag:
        """Write the contents of this model to Juju databag.

        :param databag: the databag to write the data to.
        :param clear: ensure the databag is cleared before writing it.
        """
        _databag: _RawDatabag = {} if databag is None else databag

        if clear:
            _databag.clear()

        dct = self.model_dump(mode="json", by_alias=True, exclude_defaults=True, round_trip=True)  # type: ignore
        _databag.update(dct)
        return _databag
