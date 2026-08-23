# SPDX-FileCopyrightText: 2026 Gabriel B. Furlan
# SPDX-License-Identifier: MIT
"""Client primitives for the proprietary Moni Mobile TCP protocol.

The packet layout was derived through interoperability testing. Payloads can
contain private alarm events and zone data, so this module deliberately never
logs plaintext packets, credentials, alarm codes, or session tokens.

The client stays synchronous because Home Assistant invokes it in executor
jobs. Keeping socket ownership inside one worker also makes each protocol
exchange atomic from the entity's point of view.
"""

from __future__ import annotations

import socket

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


# AES-ECB and this fixed key are requirements of the legacy wire protocol, not
# cryptographic choices made by this integration. PKCS#7 padding is applied to
# every plaintext packet before transmission.
AES_KEY = bytes.fromhex("6bfd9519cd15dfe13f2fa8eec726bb0a")

# Server acknowledgements end with the two-byte token received in the current
# challenge. Tokens must never be reused across TCP connections.
ACK_PREFIX = bytes.fromhex("010027")
COMMAND_AUTH_SUFFIX = bytes.fromhex("000027")

# Initial request packets select the operation before authentication. Event
# support is retained for protocol completeness even though state polling uses
# the richer summary request.
FIRST_PACKET_ARM_AWAY = bytes.fromhex("00ca00180027")
FIRST_PACKET_DISARM = bytes.fromhex("00cb00170027")
FIRST_PACKET_EVENT = bytes.fromhex("006a000c0027")
FIRST_PACKET_SUMMARY = bytes.fromhex("00c900100027")

# Authentication packet prefixes differ between state/event reads and commands.
COMMAND_AUTH_PREFIX = bytes.fromhex("09a3d7ef206fc52200001bdd00000164")
STATE_AUTH_PREFIX = bytes.fromhex("09a3d7ef206fc522000000000027")


class MoniMobileError(RuntimeError):
    """Base error for Moni Mobile communication."""


class MoniMobileClient:
    """Small synchronous client wrapper used from executor jobs."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        app_password: str,
        alarm_code: str,
        timeout: float = 8.0,
    ) -> None:
        """Initialize the client without logging sensitive values."""
        self.host = host
        self.port = port
        # These fields remain part of the established YAML contract. The
        # observed legacy command exchange authenticates with the alarm code;
        # username/password are retained for compatibility and future stages.
        self.username = username
        self.app_password = app_password
        self.alarm_code = alarm_code
        self.timeout = timeout

    def probe(self) -> None:
        """Check whether the Moni Mobile TCP port accepts connections."""
        # A successful probe proves only TCP reachability; it doesn't authenticate
        # or imply that a later protocol command will succeed.
        with socket.create_connection((self.host, self.port), timeout=self.timeout):
            return

    def _encrypt(self, payload: bytes) -> bytes:
        """Encrypt one protocol payload."""
        return AES.new(AES_KEY, AES.MODE_ECB).encrypt(pad(payload, AES.block_size))

    def _decrypt(self, payload: bytes) -> bytes:
        """Decrypt one protocol payload."""
        return unpad(AES.new(AES_KEY, AES.MODE_ECB).decrypt(payload), AES.block_size)

    def _recv_decrypted(self, sock: socket.socket, max_bytes: int = 4096) -> bytes:
        """Receive and decrypt one encrypted server payload."""
        encrypted = sock.recv(max_bytes)
        if not encrypted:
            raise MoniMobileError("Servidor Moni Mobile encerrou a conexao")
        if len(encrypted) % AES.block_size:
            raise MoniMobileError(
                "Pacote Moni Mobile com tamanho criptografado invalido"
            )
        return self._decrypt(encrypted)

    def _send_encrypted(self, sock: socket.socket, payload: bytes) -> None:
        """Encrypt and send one client payload."""
        sock.sendall(self._encrypt(payload))

    def _extract_token(self, challenge: bytes) -> bytes:
        """Extract the two-byte session token returned by the server."""
        # Valid challenges observed from the server start with 0x01 and carry
        # the per-connection token in their final two bytes.
        if len(challenge) < 5 or challenge[0] != 0x01:
            raise MoniMobileError("Desafio Moni Mobile invalido")
        return challenge[-2:]

    def _ack(self, token: bytes) -> bytes:
        """Build an ACK packet for the current token."""
        return ACK_PREFIX + token

    def _build_command_auth(self, token: bytes) -> bytes:
        """Build the authenticated command packet for arm/disarm."""
        code = self.alarm_code.encode("ascii")
        if len(code) > 255:
            raise MoniMobileError("Senha de comando Moni Mobile longa demais")
        # The code is length-prefixed by two reserved zero bytes and one byte of
        # length. Encoding it as text preserves leading zeroes.
        return (
            COMMAND_AUTH_PREFIX
            + bytes((0x00, 0x00, len(code)))
            + code
            + COMMAND_AUTH_SUFFIX
            + token
        )

    def _build_state_auth(self, token: bytes) -> bytes:
        """Build the authenticated pending-event query packet."""
        return STATE_AUTH_PREFIX + token

    def _build_summary_auth(self, token: bytes) -> bytes:
        """Build the authenticated alarm summary query packet."""
        return COMMAND_AUTH_PREFIX + bytes.fromhex("0027") + token

    def _exchange(self, first_packet: bytes, auth_kind: str = "command") -> bytes:
        """Run the Moni Mobile challenge/auth/response exchange."""
        with socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        ) as sock:
            sock.settimeout(self.timeout)

            # Phase 1: choose the operation and receive a fresh session token.
            self._send_encrypted(sock, first_packet)
            challenge = self._recv_decrypted(sock, AES.block_size)
            token = self._extract_token(challenge)

            # Phase 2: build the authentication shape required by that operation.
            if auth_kind == "event":
                auth_packet = self._build_state_auth(token)
            elif auth_kind == "summary":
                auth_packet = self._build_summary_auth(token)
            else:
                auth_packet = self._build_command_auth(token)
            self._send_encrypted(sock, auth_packet)

            # Phase 3: acknowledge the server's authentication response, collect
            # the operation result, and finish with a final acknowledgement.
            self._recv_decrypted(sock, AES.block_size)
            self._send_encrypted(sock, self._ack(token))
            response = self._recv_decrypted(sock)
            self._send_encrypted(sock, self._ack(token))
            return response

    def get_state(self) -> str | None:
        """Return the alarm state.

        The summary response is a compact legacy binary payload. In the
        captured Moni Mobile protocol, partition state bytes use 2 for
        disarmed and 3 for armed.
        """
        response = self._exchange(
            FIRST_PACKET_SUMMARY,
            auth_kind="summary",
        )
        if len(response) > 15:
            # The summary contains two partition status bytes. An armed partition
            # takes precedence because the alarm panel isn't fully disarmed.
            partition_states = (response[12], response[15])
            if any(state == 3 for state in partition_states):
                return "armed_away"
            if all(state == 2 for state in partition_states):
                return "disarmed"

        # Some server variants include textual state instead of the compact
        # offsets above. Latin-1 provides a lossless byte-to-text fallback.
        text = response.decode("latin1", errors="ignore").upper()
        if "DESARMADO" in text:
            return "disarmed"
        if "ARMADO" in text:
            return "armed_away"
        return None

    def arm_away(self) -> None:
        """Arm the alarm in away mode."""
        response = self._exchange(FIRST_PACKET_ARM_AWAY)
        # 00 01 00 is the positive command acknowledgement observed on the wire.
        if not response.startswith(b"\x00\x01\x00"):
            raise MoniMobileError("Servidor Moni Mobile nao confirmou o arme")

    def disarm(self) -> None:
        """Disarm the alarm."""
        response = self._exchange(FIRST_PACKET_DISARM)
        # Arm and disarm share the same positive acknowledgement signature.
        if not response.startswith(b"\x00\x01\x00"):
            raise MoniMobileError("Servidor Moni Mobile nao confirmou o desarme")
