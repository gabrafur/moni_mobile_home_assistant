# SPDX-FileCopyrightText: 2026 Gabriel B. Furlan
# SPDX-License-Identifier: MIT
"""Initialize the YAML-only Moni Mobile alarm integration.

The actual entity is created by the ``alarm_control_panel`` platform. This
module only declares that the domain is platform-only and lets Home Assistant
load the platform configuration from YAML.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


# Reject top-level options such as ``moni_mobile:``. Configuration belongs
# under ``alarm_control_panel: - platform: moni_mobile`` for compatibility
# with the integration's original deployment.
CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Confirm domain setup; the platform performs the real initialization."""
    return True
