"""Rahul Connect subsystem.

This package adds the local gateway, device registry, pairing flow, and
protocol definitions used by Rahul AI to reach companion devices.
"""

from .service import RahulConnectService, get_service

__all__ = ["RahulConnectService", "get_service"]
