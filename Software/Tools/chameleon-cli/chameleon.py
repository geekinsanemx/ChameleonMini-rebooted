#!/usr/bin/env python3
"""
chameleon.py - All-in-one CLI for the ChameleonMini RevE rebooted (and the
factory firmware, whose commands carry an 'MY' suffix -- detected automatically).

Action-flag interface. Pick ONE action and add modifiers as needed:

  Actions:
    --info                    firmware version + overview of the 8 slots
    --slots                   list slots (config/uid/memsize)
    --dump                    dump slot(s) to file             (--slot N | --all) [--out DIR]
    --upload                  upload a dump to a slot           --file F --slot N [--type CONF]
    --backup                  back up full state                (--slot N | --all) [--out DIR]
    --restore                 restore from a backup             --dir D (--slot N | --all)
    --create                  create a tag from scratch         --slot N [--type --uid --atqa --sak --file]
    --set-config CONF         set a slot's configuration        --slot N
    --set-uid HEX             set the UID                       --slot N
    --set-atqa HEX            set the ATQA                      --slot N
    --set-sak  HEX            set the SAK                       --slot N
    --detection               read detection data + point to mfkey32  --slot N [--out FILE]
    --clone                   read/crack a physical card and upload    --slot N [--type CONF]
    --read-card               read a physical card (ACR122U)    [--out FILE] [--keyfile K]
    --crack                   recover keys (ACR122U)            [--out FILE] [--darkside]
    --reset                   reset the device
    --dfu                     enter the bootloader (DFU)

  Modifiers:
    -p/--port P   --slot N   --all   --file F   -o/--out PATH   --dir D
    --type CONF   --uid HEX  --atqa HEX  --sak HEX  --darkside  --keyfile K

Examples:
    chameleon.py --info
    chameleon.py --dump --all -o backup-today
    chameleon.py --upload --file ~/card.bin --slot 4
    chameleon.py --backup --all -o bk       ;  chameleon.py --restore --all --dir bk
    chameleon.py --create --slot 5 --type MF_CLASSIC_1K_7B --uid 04112233445566 --sak 20
    chameleon.py --set-uid AABBCCDD --slot 0
    chameleon.py --clone --slot 6

CHANGELOG
  2.0.0 - Action-flag interface; backup/restore integrated.
  1.0.0 - Initial version (subcommands).
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

CURRENT_VERSION = "2.0.0"

SOH, EOT, ACK, NAK, CAN = 0x01, 0x04, 0x06, 0x15, 0x18
BLOCK_SIZE = 128
CONFIG_BY_SIZE = {320: "MF_CLASSIC_MINI", 1024: "MF_CLASSIC_1K", 4096: "MF_CLASSIC_4K"}
CLOSED = ("CLOSED", "NO CONFIGURATION", "NONE", "", None)
MFKEY32_CANDIDATES = [
    "/usr/local/src/proxmark3/tools/mfkey/mfkey32",
    "/usr/local/src/iceman1001/proxmark3/tools/mfkey/mfkey32",
    "mfkey32",
]


class ChameleonError(Exception):
    """Communication or protocol error with the device."""


def find_mfkey32():
    for c in MFKEY32_CANDIDATES:
        if os.path.isabs(c) and os.path.exists(c):
            return c
        if shutil.which(c):
            return c
    return None


# --------------------------------------------------------------------------- #
#  Device (serial)
# --------------------------------------------------------------------------- #
class Chameleon:
    def __init__(self, port=None, timeout=3.0):
        import serial
        port = port or self._autodetect_port()
        self.serial = serial.Serial(port, 115200, timeout=timeout)
        self.port = port
        time.sleep(0.6)
        self.serial.write(b"\r"); self.serial.flush(); time.sleep(0.3)
        self.serial.read(self.serial.in_waiting or 0)
        self.serial.reset_input_buffer()
        self.suffix = self._detect_suffix()

    @staticmethod
    def _autodetect_port():
        for p in sorted(glob.glob("/dev/ttyACM*")):
            return p
        raise ChameleonError("no /dev/ttyACM* found (board connected and not captured by a VM?)")

    def _detect_suffix(self):
        for suffix in ("", "MY"):
            self.suffix = suffix
            if self.command("VERSION?").startswith("1"):
                return suffix
        raise ChameleonError("device does not answer VERSION? or VERSIONMY?")

    def command(self, cmd, wait=0.6):
        name, sep, _ = cmd.partition("?")
        if sep == "?":
            full = f"{name}{self.suffix}?"
        else:
            name, delim, rest = cmd.partition("=")
            full = f"{name}{self.suffix}{delim}{rest}"
        self.serial.reset_input_buffer()
        self.serial.write((full + "\r").encode()); self.serial.flush()
        time.sleep(wait)
        return self.serial.read(self.serial.in_waiting or 1).decode("ascii", "replace").strip()

    def query(self, cmd):
        resp = self.command(cmd)
        lines = [l for l in resp.splitlines() if l.strip()]
        if not lines or not lines[0][:1] == "1":
            raise ChameleonError(f"{cmd} -> {resp!r}")
        return lines[1].strip() if len(lines) > 1 else ""

    def try_query(self, cmd):
        try:
            return self.query(cmd)
        except ChameleonError:
            return None

    def xmodem_receive(self):
        data = bytearray()
        self.serial.reset_input_buffer()
        self.serial.write(bytes([NAK])); self.serial.flush()
        expected = 1
        while True:
            b = self.serial.read(1)
            if not b:
                raise ChameleonError(f"timeout after {len(data)} bytes")
            if b[0] == EOT:
                self.serial.write(bytes([ACK])); self.serial.flush(); return bytes(data)
            if b[0] == CAN:
                raise ChameleonError("cancelled by the device")
            if b[0] != SOH:
                continue
            hdr = self.serial.read(2); blk = self.serial.read(BLOCK_SIZE); ck = self.serial.read(1)
            if len(hdr) < 2 or len(blk) < BLOCK_SIZE or not ck:
                raise ChameleonError("incomplete XMODEM frame")
            if hdr[0] != (255 - hdr[1]) or (sum(blk) & 0xFF) != ck[0]:
                self.serial.write(bytes([NAK])); self.serial.flush(); continue
            if hdr[0] == (expected & 0xFF):
                data.extend(blk); expected += 1
            self.serial.write(bytes([ACK])); self.serial.flush()

    def xmodem_send(self, data):
        if len(data) % BLOCK_SIZE:
            data += b"\x00" * (BLOCK_SIZE - len(data) % BLOCK_SIZE)
        self.serial.reset_input_buffer()
        deadline = time.time() + 15
        while time.time() < deadline:
            b = self.serial.read(1)
            if b and b[0] == NAK:
                break
            if b and b[0] == CAN:
                raise ChameleonError("cancelled before start")
        else:
            raise ChameleonError("device never requested data (no NAK)")
        for i in range(0, len(data), BLOCK_SIZE):
            chunk = data[i:i + BLOCK_SIZE]
            n = i // BLOCK_SIZE + 1
            frame = bytes([SOH, n & 0xFF, (255 - n) & 0xFF]) + chunk + bytes([sum(chunk) & 0xFF])
            for _ in range(5):
                self.serial.write(frame); self.serial.flush()
                r = self.serial.read(1)
                if r and r[0] == ACK:
                    break
                if r and r[0] == CAN:
                    raise ChameleonError(f"cancelled on frame {n}")
            else:
                raise ChameleonError(f"frame {n} not acknowledged")
        self.serial.write(bytes([EOT])); self.serial.flush(); self.serial.read(1)

    def active_slot(self):
        return self.query("SETTING?").replace("NO.", "").strip()

    def set_slot(self, n):
        if not self.command(f"SETTING={n}").startswith("1"):
            raise ChameleonError(f"slot {n} not accepted")

    def slot_info(self, n):
        self.set_slot(n)
        return {"slot": n, "config": self.try_query("CONFIG?"),
                "uid": self.try_query("UID?"), "memsize": self.try_query("MEMSIZE?"),
                "atqa": self.try_query("ATQA?"), "sak": self.try_query("SAK?")}

    def close(self):
        self.serial.close()


# --------------------------------------------------------------------------- #
#  ACR122U (host)
# --------------------------------------------------------------------------- #
def require(tool):
    if not shutil.which(tool):
        raise ChameleonError(f"'{tool}' not found on the host (install libnfc-bin / mfoc / mfcuk)")
    return tool


def acr_read_card(out_path, keyfile=None):
    require("nfc-mfclassic")
    cmd = ["nfc-mfclassic", "r", "a", out_path] + ([keyfile] if keyfile else [])
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode == 0


def acr_crack(out_path, darkside=False):
    if darkside:
        require("mfcuk")
        print("  using mfcuk (darkside)...")
        subprocess.run(["mfcuk", "-C", "-R", "0:A", "-s", "250", "-S", "250"])
        return False
    require("mfoc")
    cmd = ["mfoc", "-O", out_path]
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode == 0


# --------------------------------------------------------------------------- #
#  Actions
# --------------------------------------------------------------------------- #
def need_slot(a):
    if a.slot is None:
        raise ChameleonError("this action requires --slot N")
    return a.slot


def act_info(dev, a):
    print(f"port     : {dev.port}")
    print(f"firmware : {dev.try_query('VERSION?')}")
    print(f"commands : {dev.try_query('HELP') or '(n/a)'}")
    orig = dev.active_slot()
    print("\nslots:")
    for n in range(8):
        i = dev.slot_info(n)
        print(f"  {n}: {str(i['config']):22s} uid={i['uid']}  mem={i['memsize']}")
    dev.set_slot(orig)


def act_slots(dev, a):
    orig = dev.active_slot()
    for n in range(8):
        i = dev.slot_info(n)
        print(f"slot {n}: config={i['config']} uid={i['uid']} memsize={i['memsize']}")
    dev.set_slot(orig)


def act_set_config(dev, a):
    dev.set_slot(need_slot(a))
    if not dev.command(f"CONFIG={a.set_config}").startswith("1"):
        raise ChameleonError(f"CONFIG={a.set_config} rejected")
    print(f"slot {a.slot}: CONFIG={dev.query('CONFIG?')}")


def act_set_uid(dev, a):
    dev.set_slot(need_slot(a))
    if not dev.command(f"UID={a.set_uid}").startswith("1"):
        raise ChameleonError(f"UID={a.set_uid} rejected")
    print(f"slot {a.slot}: UID={dev.query('UID?')}")


def act_set_atqa(dev, a):
    dev.set_slot(need_slot(a))
    r = dev.command(f"ATQA={a.set_atqa}")
    print(f"slot {a.slot}: ATQA -> {r.splitlines()[0]} (now {dev.try_query('ATQA?')})")


def act_set_sak(dev, a):
    dev.set_slot(need_slot(a))
    r = dev.command(f"SAK={a.set_sak}")
    print(f"slot {a.slot}: SAK -> {r.splitlines()[0]} (now {dev.try_query('SAK?')})")


def act_create(dev, a):
    dev.set_slot(need_slot(a))
    if not dev.command(f"CONFIG={a.type}").startswith("1"):
        raise ChameleonError(f"CONFIG={a.type} rejected")
    if a.file:
        with open(a.file, "rb") as fh:
            payload = fh.read()
        if "XMODEM" in dev.command("UPLOAD", 0.6).upper():
            dev.xmodem_send(payload); time.sleep(1.0)
    if a.uid:
        dev.command(f"UID={a.uid}")
    if a.atqa:
        dev.command(f"ATQA={a.atqa}")
    if a.sak:
        dev.command(f"SAK={a.sak}")
    print(f"slot {a.slot} created: CONFIG={dev.try_query('CONFIG?')} UID={dev.try_query('UID?')} "
          f"ATQA={dev.try_query('ATQA?')} SAK={dev.try_query('SAK?')}")


def _download_slot(dev, n, outdir):
    i = dev.slot_info(n)
    if i["config"] in CLOSED:
        return i, None
    if "XMODEM" not in dev.command("DOWNLOAD", 0.6).upper():
        return i, None
    blob = dev.xmodem_receive()
    with open(os.path.join(outdir, f"slot{n}.bin"), "wb") as fh:
        fh.write(blob)
    memsize = int(i["memsize"]) if (i["memsize"] or "").isdigit() else 0
    if memsize and memsize <= len(blob):
        cfg = (i["config"] or "slot").replace("/", "_")
        with open(os.path.join(outdir, f"slot{n}_{cfg}.mfd"), "wb") as fh:
            fh.write(blob[:memsize])
    return i, len(blob)


def act_dump(dev, a):
    if not a.all and a.slot is None:
        raise ChameleonError("--dump requires --slot N or --all")
    outdir = a.out or datetime.now().strftime("dump-%y%m%d%H%M%S")
    os.makedirs(outdir, exist_ok=True)
    orig = dev.active_slot()
    for n in (range(8) if a.all else [a.slot]):
        i, size = _download_slot(dev, n, outdir)
        print(f"slot {n}: {i['config']} uid={i['uid']} -> {size if size else 'no data'}")
    dev.set_slot(orig)
    print(f"saved to: {outdir}")


def act_upload(dev, a):
    if not a.file or a.slot is None:
        raise ChameleonError("--upload requires --file F and --slot N")
    with open(a.file, "rb") as fh:
        data = fh.read()
    config = a.type or CONFIG_BY_SIZE.get(len(data))
    if not config:
        raise ChameleonError(f"cannot infer config for {len(data)} B; use --type")
    dev.set_slot(a.slot)
    if not dev.command(f"CONFIG={config}").startswith("1"):
        raise ChameleonError(f"CONFIG={config} rejected")
    if "XMODEM" not in dev.command("UPLOAD", 0.6).upper():
        raise ChameleonError("UPLOAD did not enter XMODEM mode")
    dev.xmodem_send(data); time.sleep(1.0)
    print(f"slot {a.slot}: uploaded {len(data)} B, UID={dev.try_query('UID?')}")


def act_backup(dev, a):
    if not a.all and a.slot is None:
        raise ChameleonError("--backup requires --slot N or --all")
    outdir = a.out or datetime.now().strftime("backup-%y%m%d%H%M%S")
    os.makedirs(outdir, exist_ok=True)
    orig = dev.active_slot()
    manifest = {"firmware": dev.try_query("VERSION?"),
                "created": datetime.now().isoformat(timespec="seconds"), "slots": []}
    for n in (range(8) if a.all else [a.slot]):
        i, size = _download_slot(dev, n, outdir)
        e = {"slot": n, "config": i["config"], "uid": i["uid"], "memsize": i["memsize"],
             "atqa": i["atqa"], "sak": i["sak"],
             "data_file": f"slot{n}.bin" if size else None}
        manifest["slots"].append(e)
        print(f"slot {n}: config={e['config']} uid={e['uid']} "
              f"{'data '+e['data_file'] if e['data_file'] else '(no data)'}")
    dev.set_slot(orig)
    with open(os.path.join(outdir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"backup at: {outdir}")


def _restore_slot(dev, e, srcdir):
    n = e["slot"]; dev.set_slot(n)
    if e["config"] in CLOSED:
        dev.command("CLEAR"); return f"slot {n}: CLOSED"
    if not dev.command(f"CONFIG={e['config']}").startswith("1"):
        return f"slot {n}: CONFIG={e['config']} REJECTED"
    if e.get("data_file"):
        with open(os.path.join(srcdir, e["data_file"]), "rb") as fh:
            data = fh.read()
        if "XMODEM" in dev.command("UPLOAD", 0.6).upper():
            dev.xmodem_send(data); time.sleep(1.0)
    for field, cmd in (("uid", "UID"), ("atqa", "ATQA"), ("sak", "SAK")):
        if e.get(field):
            dev.command(f"{cmd}={e[field]}")
    return f"slot {n}: config={dev.try_query('CONFIG?')} uid={dev.try_query('UID?')}"


def act_restore(dev, a):
    if not a.dir:
        raise ChameleonError("--restore requires --dir D")
    if not a.all and a.slot is None:
        raise ChameleonError("--restore requires --slot N or --all")
    with open(os.path.join(a.dir, "manifest.json")) as fh:
        manifest = json.load(fh)
    fw = dev.try_query("VERSION?")
    if manifest.get("firmware") and fw and manifest["firmware"].split()[0] != fw.split()[0]:
        print(f"warning: backup from '{manifest['firmware']}' -> device '{fw}'")
    orig = dev.active_slot()
    entries = manifest["slots"] if a.all else [e for e in manifest["slots"] if e["slot"] == a.slot]
    if not entries:
        raise ChameleonError(f"the backup does not contain slot {a.slot}")
    for e in entries:
        print(_restore_slot(dev, e, a.dir))
    dev.set_slot(orig)
    print("restore complete")


def act_detection(dev, a):
    dev.set_slot(need_slot(a))
    cfg = dev.try_query("CONFIG?")
    if cfg and "DETECTION" not in cfg:
        print(f"warning: slot {a.slot} is {cfg}, not a detection slot")
    dev.command("DETECTION", 0.6); time.sleep(0.5)
    raw = dev.serial.read(dev.serial.in_waiting or 1)
    out = a.out or f"detection-slot{a.slot}.bin"
    with open(out, "wb") as fh:
        fh.write(raw)
    print(f"detection data: {len(raw)} B -> {out}")
    mk = find_mfkey32()
    print(f"mfkey32: {mk}" if mk else "mfkey32 not found; raw saved for manual processing")


def act_clone(dev, a):
    n = need_slot(a)
    tmp = datetime.now().strftime("clone-%y%m%d%H%M%S.mfd")
    print("[1/2] reading the physical card with the ACR122U...")
    if not (acr_read_card(tmp) or acr_crack(tmp)) or not os.path.exists(tmp):
        raise ChameleonError("could not read/crack the physical card")
    print(f"[2/2] uploading {tmp} to slot {n}...")
    a.file = tmp
    act_upload(dev, a)


def act_read_card(dev, a):
    out = a.out or datetime.now().strftime("card-%y%m%d%H%M%S.mfd")
    ok = acr_read_card(out, a.keyfile)
    print(f"{'OK' if ok else 'FAILED'} -> {out}")


def act_crack(dev, a):
    out = a.out or datetime.now().strftime("card-%y%m%d%H%M%S.mfd")
    ok = acr_crack(out, a.darkside)
    print(f"{'OK' if ok else 'check the output'} -> {out}")


def act_reset(dev, a):
    print(dev.command("RESET").splitlines()[0])


def act_dfu(dev, a):
    print("entering DFU; the board will re-enumerate as 03eb:2fe4")
    try:
        dev.command("UPGRADE", 0.3)
    except Exception:
        pass


# action name -> (handler, needs_serial)
ACTIONS = {
    "info": (act_info, True), "slots": (act_slots, True),
    "dump": (act_dump, True), "upload": (act_upload, True),
    "backup": (act_backup, True), "restore": (act_restore, True),
    "create": (act_create, True),
    "set_config": (act_set_config, True), "set_uid": (act_set_uid, True),
    "set_atqa": (act_set_atqa, True), "set_sak": (act_set_sak, True),
    "detection": (act_detection, True), "clone": (act_clone, True),
    "read_card": (act_read_card, False), "crack": (act_crack, False),
    "reset": (act_reset, True), "dfu": (act_dfu, True),
}


def build_parser():
    p = argparse.ArgumentParser(
        description="All-in-one CLI for the ChameleonMini RevE rebooted",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-p", "--port", help="serial port (autodetects /dev/ttyACM*)")
    p.add_argument("-V", "--version", action="version", version=CURRENT_VERSION)

    g = p.add_argument_group("actions (pick ONE)")
    m = g.add_mutually_exclusive_group(required=True)
    for flag in ("info", "slots", "dump", "upload", "backup", "restore", "create",
                 "detection", "clone", "read-card", "crack", "reset", "dfu"):
        m.add_argument(f"--{flag}", action="store_true", help=f"action: {flag}")
    m.add_argument("--set-config", metavar="CONF", help="set --slot's configuration")
    m.add_argument("--set-uid", metavar="HEX", help="set --slot's UID")
    m.add_argument("--set-atqa", metavar="HEX", help="set --slot's ATQA")
    m.add_argument("--set-sak", metavar="HEX", help="set --slot's SAK")

    o = p.add_argument_group("modifiers")
    o.add_argument("--slot", type=int, help="target slot (0-7)")
    o.add_argument("--all", action="store_true", help="all slots (dump/backup/restore)")
    o.add_argument("--file", help="data file (upload/create)")
    o.add_argument("-o", "--out", help="output file/directory")
    o.add_argument("--dir", help="backup directory (restore)")
    o.add_argument("--type", default="MF_CLASSIC_1K", help="config (upload/create), default MF_CLASSIC_1K")
    o.add_argument("--uid", help="UID for --create")
    o.add_argument("--atqa", help="ATQA for --create")
    o.add_argument("--sak", help="SAK for --create")
    o.add_argument("--darkside", action="store_true", help="use mfcuk for --crack")
    o.add_argument("--keyfile", help="key file for --read-card")
    return p


def selected_action(a):
    for name in ("info", "slots", "dump", "upload", "backup", "restore", "create",
                 "detection", "clone", "read_card", "crack", "reset", "dfu"):
        if getattr(a, name):
            return name
    for name in ("set_config", "set_uid", "set_atqa", "set_sak"):
        if getattr(a, name) is not None:
            return name
    return None


def main():
    a = build_parser().parse_args()
    action = selected_action(a)
    handler, needs_serial = ACTIONS[action]
    dev = None
    try:
        if needs_serial:
            dev = Chameleon(a.port)
        handler(dev, a)
    except ChameleonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if dev:
            dev.close()


if __name__ == "__main__":
    main()
