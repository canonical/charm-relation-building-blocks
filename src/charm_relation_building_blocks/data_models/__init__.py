# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable models for Juju relation data."""

from .databagmodel import DatabagModel, DataValidationError

__all__ = [DatabagModel, DataValidationError]
