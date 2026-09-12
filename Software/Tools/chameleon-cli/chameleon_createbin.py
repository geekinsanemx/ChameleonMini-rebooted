#!/usr/bin/env python3
"""
chameleon_createbin.py - Produces the encrypted .bin files that BOOT_LOADER_EXE.exe
expects for the locked bootloader of the ChameleonMini RevE rebooted.

Equivalent to Createbin.exe (Windows) and to the 'createbin' operation in
Software/Tools/crypt_operations.py, which does not run under Python 3.

Format: pad to a multiple of 16 with zeros, append 16 bytes of 0xCD, and for
each 16-byte block an incremental XOR (0x2D + offset) followed by an AES decrypt.

CHANGELOG
  1.0.0 - Initial version, ported to Python 3 / pycryptodome.
"""

import argparse
import subprocess

from Crypto.Cipher import AES

CURRENT_VERSION = "1.0.0"

AES_KEY = b"designed by dxls"
BLOCK = 16
SCRAMBLE_SEED = 0x2D
TRAILER_BYTE = 0xCD


def createbin(data):
    if len(data) % BLOCK != 0:
        data += b"\0" * (BLOCK - len(data) % BLOCK)
    data += bytes([TRAILER_BYTE]) * BLOCK

    out = bytearray()
    for offset in range(0, len(data), BLOCK):
        block = data[offset:offset + BLOCK]
        scrambled = bytes((block[j] ^ ((SCRAMBLE_SEED + offset + j) & 0xFF)) for j in range(BLOCK))
        cipher = AES.new(AES_KEY, AES.MODE_CBC, bytes(BLOCK))
        out += cipher.decrypt(scrambled)
    return bytes(out)


def ihex_to_bin(path):
    return subprocess.run(
        ["avr-objcopy", "-I", "ihex", path, "-O", "binary", "/dev/stdout"],
        check=True, stdout=subprocess.PIPE).stdout


def main():
    parser = argparse.ArgumentParser(description="Encrypt firmware for the RevE rebooted bootloader")
    parser.add_argument("input", help="an .hex (ihex) or .bin (raw binary) file")
    parser.add_argument("output", help="encrypted .bin output file")
    parser.add_argument("-V", "--version", action="version", version=CURRENT_VERSION)
    args = parser.parse_args()

    raw = ihex_to_bin(args.input) if args.input.lower().endswith((".hex", ".eep")) else open(args.input, "rb").read()
    encoded = createbin(raw)
    with open(args.output, "wb") as handle:
        handle.write(encoded)
    print(f"{args.input}: {len(raw)} B -> {args.output}: {len(encoded)} B")


if __name__ == "__main__":
    main()
