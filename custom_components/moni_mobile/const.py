# SPDX-FileCopyrightText: 2026 Gabriel B. Furlan
# SPDX-License-Identifier: MIT
"""Constants shared by the Moni Mobile integration modules."""

# Home Assistant integration identity and default presentation.
DOMAIN = "moni_mobile"
DEFAULT_NAME = "Alarme Moni Mobile"

# YAML keys specific to the Moni Mobile platform. Generic host, port, username,
# and name keys come from ``homeassistant.const`` at their call site.
CONF_ALARM_CODE = "code"
CONF_APP_PASSWORD = "password"

# Entity attributes intentionally limited to operational diagnostics.
ATTR_PROTOCOL_STAGE = "protocol_stage"
ATTR_LAST_ERROR = "last_error"
ATTR_HOST = "host"
ATTR_PORT = "port"
