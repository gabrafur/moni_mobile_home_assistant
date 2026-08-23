# Moni Mobile Alarm for Home Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Custom Home Assistant integration for locally polling and controlling alarm
accounts that expose the proprietary Moni Mobile TCP protocol.

The integration provides an `alarm_control_panel` entity with state polling,
away arming, and disarming. Configuration remains YAML-based so existing
installations can migrate without changing their secrets or entity IDs.

## Installation with HACS

1. In HACS, open **Integrations** and add
   `https://github.com/gabrafur/moni_mobile_home_assistant` as a custom
   repository of type **Integration**.
2. Install **Moni Mobile Alarm**.
3. Restart Home Assistant.
4. Add the YAML configuration below and restart Home Assistant again.

## Configuration

Store the values in `secrets.yaml`; keep the alarm code quoted when it starts
with zero.

```yaml
moni_mobile_host: alarmsystem.example.net
moni_mobile_port: 7000
moni_mobile_username: "YOUR_USERNAME"
moni_mobile_app_password: "YOUR_APP_PASSWORD"
moni_mobile_alarm_code: "0123"
```

Then configure the platform in `configuration.yaml` or in a package:

```yaml
alarm_control_panel:
  - platform: moni_mobile
    name: Moni Mobile Alarm
    host: !secret moni_mobile_host
    port: !secret moni_mobile_port
    username: !secret moni_mobile_username
    password: !secret moni_mobile_app_password
    code: !secret moni_mobile_alarm_code
```

## Supported behavior

- Polls the remote TCP endpoint for `armed_away` and `disarmed` state.
- Arms in away mode through `alarm_control_panel.alarm_arm_away`.
- Disarms through `alarm_control_panel.alarm_disarm`.
- Preserves the existing YAML schema and entity unique ID during migration.

The server can briefly report an unknown state immediately after a command
while its partition summary catches up. The integration does not log decrypted
protocol payloads because they can contain private alarm events and zone data.

## Development

Run the protocol unit tests without contacting a real alarm server:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

GitHub Actions validate the repository with HACS, hassfest, and the unit tests.
The integration ships its official brand icon through Home Assistant's local
brands proxy and publishes versioned GitHub releases.

Dependency and implementation origins are documented in
[DEPENDENCY_PROVENANCE.md](DEPENDENCY_PROVENANCE.md).

## License

Copyright (c) 2026 Gabriel B. Furlan. Distributed under the [MIT License](LICENSE).
Python source files also carry SPDX identifiers so automated scanners can
associate them with the repository license unambiguously.
