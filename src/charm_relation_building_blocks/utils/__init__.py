# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable models for Juju relation data."""

from .relation_databag import dump_to_databag, load_from_databag

__all__ = [dump_to_databag, load_from_databag]
