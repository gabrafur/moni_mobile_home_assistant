# SPDX-FileCopyrightText: 2026 Gabriel B. Furlan
# SPDX-License-Identifier: MIT
"""Unit tests for the Moni Mobile protocol client."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


CLIENT_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "moni_mobile"
    / "client.py"
)
SPEC = importlib.util.spec_from_file_location("moni_mobile_client", CLIENT_PATH)
assert SPEC is not None and SPEC.loader is not None
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


def make_client(alarm_code: str = "0123"):
    """Create a client with synthetic credentials."""
    return CLIENT.MoniMobileClient(
        host="alarmsystem.example.net",
        port=7000,
        username="example_user",
        app_password="example_password",
        alarm_code=alarm_code,
    )


class MoniMobileClientTest(unittest.TestCase):
    """Exercise packet construction and response parsing offline."""

    def test_encrypt_decrypt_round_trip(self) -> None:
        client = make_client()
        payload = b"synthetic protocol payload"

        self.assertEqual(client._decrypt(client._encrypt(payload)), payload)

    def test_command_auth_preserves_leading_zero(self) -> None:
        packet = make_client("0123")._build_command_auth(b"\x12\x34")

        self.assertIn(b"\x00\x00\x040123", packet)
        self.assertTrue(packet.endswith(CLIENT.COMMAND_AUTH_SUFFIX + b"\x12\x34"))

    def test_state_prefers_armed_partition(self) -> None:
        response = bytearray(16)
        response[12] = 2
        response[15] = 3
        client = make_client()

        with patch.object(client, "_exchange", return_value=bytes(response)):
            self.assertEqual(client.get_state(), "armed_away")

    def test_state_reports_disarmed_partitions(self) -> None:
        response = bytearray(16)
        response[12] = 2
        response[15] = 2
        client = make_client()

        with patch.object(client, "_exchange", return_value=bytes(response)):
            self.assertEqual(client.get_state(), "disarmed")

    def test_arm_rejects_unconfirmed_response(self) -> None:
        client = make_client()

        with patch.object(client, "_exchange", return_value=b"\x00\x00\x00"):
            with self.assertRaises(CLIENT.MoniMobileError):
                client.arm_away()


if __name__ == "__main__":
    unittest.main()
