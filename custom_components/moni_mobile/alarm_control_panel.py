# SPDX-FileCopyrightText: 2026 Gabriel B. Furlan
# SPDX-License-Identifier: MIT
"""Expose a Moni Mobile TCP account as a Home Assistant alarm panel.

The proprietary client is synchronous, so every network or disk operation is
sent to Home Assistant's executor. The entity polls because the legacy TCP
service doesn't provide a push subscription for partition state.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import MoniMobileClient, MoniMobileError
from .const import (
    ATTR_HOST,
    ATTR_LAST_ERROR,
    ATTR_PORT,
    ATTR_PROTOCOL_STAGE,
    CONF_ALARM_CODE,
    CONF_APP_PASSWORD,
    DEFAULT_NAME,
)

# Home Assistant moved these constants to enums over time. Keep the fallback so
# existing installations can migrate to HACS without changing their HA version.
try:
    from homeassistant.components.alarm_control_panel import (
        AlarmControlPanelEntityFeature,
    )
except ImportError:  # pragma: no cover - compatibility with older HA.
    AlarmControlPanelEntityFeature = None

try:
    from homeassistant.components.alarm_control_panel import AlarmControlPanelState

    STATE_ALARM_ARMED_AWAY = AlarmControlPanelState.ARMED_AWAY
    STATE_ALARM_DISARMED = AlarmControlPanelState.DISARMED
except ImportError:  # pragma: no cover - compatibility with older HA.
    from homeassistant.const import STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED

_LOGGER = logging.getLogger(__name__)

# YAML parsers may coerce an unquoted code such as 0123 to a number. Reading the
# original scalar keeps leading zeroes intact while the configured value remains
# a safe fallback for installations that don't use the conventional secret key.
_RAW_ALARM_CODE_RE = re.compile(
    r"^\s*moni_mobile_alarm_code:\s*(?P<value>[^#\r\n]+?)\s*(?:#.*)?$",
    re.MULTILINE,
)

# Keep the public YAML contract stable during extraction from the smart-home
# monorepo. Credentials remain in ``secrets.yaml`` and are never logged here.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_APP_PASSWORD): cv.string,
        vol.Required(CONF_ALARM_CODE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up the Moni Mobile alarm platform from YAML."""
    # ``Path.read_text`` is blocking I/O, even though the secrets file is small.
    # Running it in the executor keeps Home Assistant's event loop responsive.
    alarm_code = await hass.async_add_executor_job(
        _read_raw_alarm_code, config[CONF_ALARM_CODE]
    )
    client = MoniMobileClient(
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        username=config[CONF_USERNAME],
        app_password=config[CONF_APP_PASSWORD],
        alarm_code=alarm_code,
    )
    async_add_entities([MoniMobileAlarm(hass, config[CONF_NAME], client)], True)


def _read_raw_alarm_code(fallback: str) -> str:
    """Read the alarm code while preserving leading zeros from secrets.yaml."""
    secrets_path = Path("/config/secrets.yaml")
    if not secrets_path.exists():
        return str(fallback)

    match = _RAW_ALARM_CODE_RE.search(secrets_path.read_text(encoding="utf-8"))
    if not match:
        return str(fallback)

    value = match.group("value").strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value


class MoniMobileAlarm(AlarmControlPanelEntity):
    """Home Assistant entity for a Moni Mobile alarm account."""

    # The server offers request/response exchanges rather than state callbacks.
    _attr_should_poll = True

    def __init__(
        self, hass: HomeAssistant, name: str, client: MoniMobileClient
    ) -> None:
        """Initialize the alarm entity."""
        self.hass = hass
        self._attr_name = name
        # Preserve the pre-HACS identity so migration doesn't create a duplicate
        # entity in Home Assistant's entity registry.
        self._attr_unique_id = f"moni_mobile_{client.host}_{client.port}"
        self._client = client
        self._state = None
        self._available = False
        self._last_error: str | None = None

    @property
    def state(self):
        """Return the current alarm state."""
        return self._state

    @property
    def available(self) -> bool:
        """Return whether the TCP endpoint is reachable."""
        return self._available

    @property
    def supported_features(self) -> int:
        """Return supported alarm features."""
        if AlarmControlPanelEntityFeature is None:
            return 0
        return AlarmControlPanelEntityFeature.ARM_AWAY

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        """Expose non-sensitive diagnostics."""
        # Never expose account passwords, alarm codes, tokens, or decrypted
        # payloads. Stage and last error are sufficient for troubleshooting.
        return {
            ATTR_HOST: self._client.host,
            ATTR_PORT: self._client.port,
            ATTR_PROTOCOL_STAGE: "tcp_handshake_discovery",
            ATTR_LAST_ERROR: self._last_error,
        }

    async def async_update(self) -> None:
        """Update connectivity and known state."""
        try:
            state = await self.hass.async_add_executor_job(self._client.get_state)
        except Exception as exc:  # noqa: BLE001 - report as entity diagnostic.
            # Network, padding, and protocol failures all mean the entity cannot
            # currently provide a trustworthy state; keep Home Assistant alive.
            self._available = False
            self._last_error = str(exc)
            return

        self._available = True
        self._last_error = None
        if state == "armed_away":
            self._state = STATE_ALARM_ARMED_AWAY
        elif state == "disarmed":
            self._state = STATE_ALARM_DISARMED
        else:
            self._state = None

    async def async_alarm_arm_away(self, code=None) -> None:
        """Arm the alarm in away mode."""
        try:
            await self.hass.async_add_executor_job(self._client.arm_away)
        except MoniMobileError as exc:
            self._last_error = str(exc)
            raise HomeAssistantError(str(exc)) from exc
        _LOGGER.info("Moni Mobile alarm arm command accepted")
        # Publish the accepted command immediately. The next poll reconciles it
        # with the partition summary once the remote server catches up.
        self._state = STATE_ALARM_ARMED_AWAY

    async def async_alarm_disarm(self, code=None) -> None:
        """Disarm the alarm."""
        try:
            await self.hass.async_add_executor_job(self._client.disarm)
        except MoniMobileError as exc:
            self._last_error = str(exc)
            raise HomeAssistantError(str(exc)) from exc
        _LOGGER.info("Moni Mobile alarm disarm command accepted")
        # As with arming, polling remains authoritative after this optimistic
        # state update.
        self._state = STATE_ALARM_DISARMED
