"""
hash_util.py — Attestation hash computation and algod round query.

All hash logic lives here so oracle.py and chain.py stay clean.
"""

import hashlib
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from algosdk.v2client.algod import AlgodClient


def get_current_round(algod_client: "AlgodClient") -> int:
    """Query the algod node for the most recently committed round.

    Args:
        algod_client: An initialised algosdk AlgodClient.

    Returns:
        The last-round integer from the node status response.
    """
    status = algod_client.status()
    return int(status["last-round"])


def compute_attestation_hash(
    sender_address: str,
    amount_microalgo: int,
    current_round: int,
) -> bytes:
    """Compute the 32-byte attestation hash that matches the on-chain formula.

    The contract verifies this hash when ``skip_attestation == 0``.  The
    formula is:

    .. code-block:: text

        sha256(
            decode_address(sender)   # 32 bytes
            + itob(amount)           # 8 bytes big-endian uint64
            + itob(round)            # 8 bytes big-endian uint64
        )

    Args:
        sender_address: Algorand address string of the drawing agent.
        amount_microalgo: Draw amount in microALGO (must match draw() call).
        current_round: Current Algorand round from ``algod.status()["last-round"]``.

    Returns:
        32-byte SHA-256 digest as :class:`bytes`.
    """
    from algosdk import encoding

    sender_bytes = encoding.decode_address(sender_address)  # 32 bytes
    amount_bytes = struct.pack(">Q", amount_microalgo)       # 8 bytes big-endian
    round_bytes = struct.pack(">Q", current_round)           # 8 bytes big-endian
    return hashlib.sha256(sender_bytes + amount_bytes + round_bytes).digest()


def demo_hash() -> bytes:
    """Return 32 zero bytes for use in demo mode.

    When the contract global state ``skip_attestation == 1`` (the default for
    testnet demo deployments), the contract does not verify the hash at all.
    Pass this value to ``draw()`` to avoid computing the real hash.

    Returns:
        :class:`bytes` of exactly 32 zero bytes.
    """
    return bytes(32)
