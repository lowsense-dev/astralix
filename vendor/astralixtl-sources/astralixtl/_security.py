"""Limits and validation for data received from remote peers."""

MAX_PACKET_SIZE = 16 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 16 * 1024 * 1024
MAX_WEB_DOCUMENT_SIZE = 256 * 1024 * 1024

TELEGRAM_DH_PRIME = bytes.fromhex("c71caeb9c6b1c9048e6c522f70f13f73980d40238e3e21c14934d037563d930f48198a0aa7c14058229493d22530f4dbfa336f6e0ac925139543aed44cce7c3720fd51f69458705ac68cd4fe6b6b13abdc9746512969328454f18faf8c595f642477fe96bb2a941d5bcd1d4ac8cc49880708fa9b378e3c4f3a9060bee67cf9a4a4a695811051907e162753b56b0f6b410dba74d8a84b2a14b3144e0ef1284754fd17ed950d5965b4b9dd46582db1178d169c6bc465b0d6ff9ca3928fef5b9ae4e418fc15e83ebea0f87fa9ff5eed70050ded2849f47bf959d956850ce929851f0d8115f635b105ee2e4e15d04b2454bf6f4fadf034b10403119cd8e3b92fcc5b")


def validate_packet_length(length, minimum=4):
    if not minimum <= length <= MAX_PACKET_SIZE:
        raise ValueError("Invalid or oversized MTProto packet length")
    return length
