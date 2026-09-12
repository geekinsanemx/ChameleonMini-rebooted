#!/usr/bin/env python3
"""
chameleon.py - CLI todo-en-uno para ChameleonMini RevE rebooted (y firmware de
fabrica con comandos sufijados 'MY', detectado automaticamente).

Integra el dispositivo (por puerto serie) con el ecosistema NFC del host
(ACR122U via libnfc: nfc-mfclassic, mfoc, mfcuk, mfkey32) para cubrir el flujo
completo: emular, volcar, escribir, crear tags, recuperar claves y clonar.

Subcomandos:
    info                 version del firmware y resumen de los 8 slots
    slots                lista los slots (config + uid)
    config SLOT CONF     fija la configuracion de un slot
    setuid SLOT HEX      fija el UID de un slot
    atqa SLOT HEX        fija el ATQA (rebooted)
    sak  SLOT HEX        fija el SAK  (rebooted)
    create SLOT          crea un tag desde cero (--config --uid --atqa --sak --data)
    dump                 vuelca slot(s) del dispositivo a fichero  (--slot N | --all)
    upload FILE SLOT     sube un volcado a un slot
    read-card            lee una tarjeta fisica con el ACR122U (claves por defecto)
    crack                recupera claves de una tarjeta fisica (mfoc; --darkside usa mfcuk)
    clone SLOT           lee/crackea una tarjeta fisica y la sube a un slot
    detection SLOT       lee los datos de deteccion de un slot y corre mfkey32
    reset                reinicia el dispositivo
    dfu                  entra en modo bootloader (DFU) para flashear

CHANGELOG
  1.0.0 - Version inicial.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

CURRENT_VERSION = "1.0.0"

SOH, EOT, ACK, NAK, CAN = 0x01, 0x04, 0x06, 0x15, 0x18
BLOCK_SIZE = 128

CONFIG_BY_SIZE = {320: "MF_CLASSIC_MINI", 1024: "MF_CLASSIC_1K", 4096: "MF_CLASSIC_4K"}

# Herramientas del host que se usan bajo demanda.
MFKEY32_CANDIDATES = [
    "/usr/local/src/proxmark3/tools/mfkey/mfkey32",
    "/usr/local/src/iceman1001/proxmark3/tools/mfkey/mfkey32",
    "mfkey32",
]


class ChameleonError(Exception):
    """Error de comunicacion o protocolo con el dispositivo."""


def find_mfkey32():
    for c in MFKEY32_CANDIDATES:
        if os.path.isabs(c) and os.path.exists(c):
            return c
        if shutil.which(c):
            return c
    return None


# --------------------------------------------------------------------------- #
#  Dispositivo (serie)
# --------------------------------------------------------------------------- #
class Chameleon:
    def __init__(self, port=None, timeout=3.0):
        import serial  # import diferido: solo hace falta para hablar con el device
        self._serial_mod = serial
        port = port or self._autodetect_port()
        self.serial = serial.Serial(port, 115200, timeout=timeout)
        self.port = port
        time.sleep(0.6)
        self.serial.write(b"\r")
        self.serial.flush()
        time.sleep(0.3)
        self.serial.read(self.serial.in_waiting or 0)
        self.serial.reset_input_buffer()
        self.suffix = self._detect_suffix()

    @staticmethod
    def _autodetect_port():
        for p in sorted(glob.glob("/dev/ttyACM*")):
            return p
        raise ChameleonError("no encuentro /dev/ttyACM* (¿placa conectada y no capturada por una VM?)")

    def _detect_suffix(self):
        for suffix in ("", "MY"):
            self.suffix = suffix
            if self.command("VERSION?").startswith("1"):
                return suffix
        raise ChameleonError("el dispositivo no responde a VERSION? ni VERSIONMY?")

    def command(self, cmd, wait=0.6):
        name, sep, _ = cmd.partition("?")
        if sep == "?":
            full = f"{name}{self.suffix}?"
        else:
            name, delim, rest = cmd.partition("=")
            full = f"{name}{self.suffix}{delim}{rest}"
        self.serial.reset_input_buffer()
        self.serial.write((full + "\r").encode())
        self.serial.flush()
        time.sleep(wait)
        return self.serial.read(self.serial.in_waiting or 1).decode("ascii", "replace").strip()

    def query(self, cmd):
        resp = self.command(cmd)
        lines = [l for l in resp.splitlines() if l.strip()]
        if not lines or not lines[0][:3].startswith("1"):
            raise ChameleonError(f"{cmd} -> {resp!r}")
        return lines[1].strip() if len(lines) > 1 else ""

    def try_query(self, cmd):
        try:
            return self.query(cmd)
        except ChameleonError:
            return None

    # ---- XMODEM ---------------------------------------------------------- #
    def xmodem_receive(self):
        data = bytearray()
        self.serial.reset_input_buffer()
        self.serial.write(bytes([NAK]))
        self.serial.flush()
        expected = 1
        while True:
            b = self.serial.read(1)
            if not b:
                raise ChameleonError(f"timeout tras {len(data)} bytes")
            if b[0] == EOT:
                self.serial.write(bytes([ACK])); self.serial.flush()
                return bytes(data)
            if b[0] == CAN:
                raise ChameleonError("cancelado por el dispositivo")
            if b[0] != SOH:
                continue
            hdr = self.serial.read(2); blk = self.serial.read(BLOCK_SIZE); ck = self.serial.read(1)
            if len(hdr) < 2 or len(blk) < BLOCK_SIZE or not ck:
                raise ChameleonError("trama XMODEM incompleta")
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
                raise ChameleonError("cancelado antes de empezar")
        else:
            raise ChameleonError("el dispositivo no pidio datos (sin NAK)")
        for i in range(0, len(data), BLOCK_SIZE):
            chunk = data[i:i + BLOCK_SIZE]
            frame = bytes([SOH, (i // BLOCK_SIZE + 1) & 0xFF, (255 - (i // BLOCK_SIZE + 1)) & 0xFF])
            frame += chunk + bytes([sum(chunk) & 0xFF])
            for _ in range(5):
                self.serial.write(frame); self.serial.flush()
                r = self.serial.read(1)
                if r and r[0] == ACK:
                    break
                if r and r[0] == CAN:
                    raise ChameleonError(f"cancelado en la trama {i // BLOCK_SIZE + 1}")
            else:
                raise ChameleonError(f"trama {i // BLOCK_SIZE + 1} no confirmada")
        self.serial.write(bytes([EOT])); self.serial.flush(); self.serial.read(1)

    # ---- helpers de estado ---------------------------------------------- #
    def active_slot(self):
        return self.query("SETTING?").replace("NO.", "").strip()

    def set_slot(self, n):
        if not self.command(f"SETTING={n}").startswith("1"):
            raise ChameleonError(f"slot {n} no aceptado")

    def slot_info(self, n):
        self.set_slot(n)
        return {"slot": n, "config": self.try_query("CONFIG?"),
                "uid": self.try_query("UID?"), "memsize": self.try_query("MEMSIZE?")}

    def close(self):
        self.serial.close()


# --------------------------------------------------------------------------- #
#  ACR122U (host, via libnfc)
# --------------------------------------------------------------------------- #
def require(tool):
    if not shutil.which(tool):
        raise ChameleonError(f"falta '{tool}' en el host (instala libnfc-bin / mfoc / mfcuk)")
    return tool


def acr_read_card(out_path, keyfile=None):
    require("nfc-mfclassic")
    cmd = ["nfc-mfclassic", "r", "a", out_path]
    if keyfile:
        cmd.append(keyfile)
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode == 0


def acr_crack(out_path, darkside=False):
    if darkside:
        require("mfcuk")
        print("  usando mfcuk (darkside) ...")
        subprocess.run(["mfcuk", "-C", "-R", "0:A", "-s", "250", "-S", "250"])
        return False  # mfcuk recupera una clave; el flujo completo con mfoc es preferible
    require("mfoc")
    cmd = ["mfoc", "-O", out_path]
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode == 0


# --------------------------------------------------------------------------- #
#  Subcomandos
# --------------------------------------------------------------------------- #
def cmd_info(dev, args):
    print(f"puerto   : {dev.port}")
    print(f"firmware : {dev.try_query('VERSION?')}")
    print(f"comandos : {dev.try_query('HELP') or '(n/d)'}")
    orig = dev.active_slot()
    print("\nslots:")
    for n in range(8):
        i = dev.slot_info(n)
        print(f"  {n}: {str(i['config']):22s} uid={i['uid']}  mem={i['memsize']}")
    dev.set_slot(orig)


def cmd_slots(dev, args):
    orig = dev.active_slot()
    for n in range(8):
        i = dev.slot_info(n)
        print(f"slot {n}: config={i['config']} uid={i['uid']} memsize={i['memsize']}")
    dev.set_slot(orig)


def cmd_config(dev, args):
    dev.set_slot(args.slot)
    r = dev.command(f"CONFIG={args.config}")
    if not r.startswith("1"):
        raise ChameleonError(f"CONFIG={args.config} -> {r}")
    print(f"slot {args.slot}: CONFIG={dev.query('CONFIG?')}")


def cmd_setuid(dev, args):
    dev.set_slot(args.slot)
    r = dev.command(f"UID={args.hex}")
    if not r.startswith("1"):
        raise ChameleonError(f"UID={args.hex} -> {r}")
    print(f"slot {args.slot}: UID={dev.query('UID?')}")


def cmd_atqa(dev, args):
    dev.set_slot(args.slot)
    r = dev.command(f"ATQA={args.hex}")
    print(f"slot {args.slot}: ATQA -> {r.splitlines()[0]} (ahora {dev.try_query('ATQA?')})")


def cmd_sak(dev, args):
    dev.set_slot(args.slot)
    r = dev.command(f"SAK={args.hex}")
    print(f"slot {args.slot}: SAK -> {r.splitlines()[0]} (ahora {dev.try_query('SAK?')})")


def cmd_create(dev, args):
    dev.set_slot(args.slot)
    if not dev.command(f"CONFIG={args.config}").startswith("1"):
        raise ChameleonError(f"CONFIG={args.config} rechazado")
    if args.uid:
        dev.command(f"UID={args.uid}")
    if args.atqa:
        dev.command(f"ATQA={args.atqa}")
    if args.sak:
        dev.command(f"SAK={args.sak}")
    if args.data:
        with open(args.data, "rb") as fh:
            payload = fh.read()
        if "XMODEM" in dev.command("UPLOAD", 0.6).upper():
            dev.xmodem_send(payload)
            time.sleep(1.0)
    print(f"slot {args.slot} creado: CONFIG={dev.try_query('CONFIG?')} "
          f"UID={dev.try_query('UID?')} ATQA={dev.try_query('ATQA?')} SAK={dev.try_query('SAK?')}")


def _dump_slot(dev, n, outdir):
    i = dev.slot_info(n)
    memsize = int(i["memsize"]) if i["memsize"] and i["memsize"].isdigit() else 0
    if "XMODEM" not in dev.command("DOWNLOAD", 0.6).upper():
        return None
    blob = dev.xmodem_receive()
    raw = os.path.join(outdir, f"slot{n}.bin")
    with open(raw, "wb") as fh:
        fh.write(blob)
    if memsize and memsize <= len(blob):
        cfg = (i["config"] or "slot").replace("/", "_")
        with open(os.path.join(outdir, f"slot{n}_{cfg}.mfd"), "wb") as fh:
            fh.write(blob[:memsize])
    return i, len(blob)


def cmd_dump(dev, args):
    outdir = args.outdir or datetime.now().strftime("dump-%y%m%d%H%M%S")
    os.makedirs(outdir, exist_ok=True)
    orig = dev.active_slot()
    targets = range(8) if args.all else [args.slot]
    for n in targets:
        res = _dump_slot(dev, n, outdir)
        if res:
            i, size = res
            print(f"slot {n}: {i['config']} uid={i['uid']} -> {size} B")
        else:
            print(f"slot {n}: DOWNLOAD no disponible")
    dev.set_slot(orig)
    print(f"guardado en: {outdir}")


def cmd_upload(dev, args):
    with open(args.file, "rb") as fh:
        data = fh.read()
    config = args.config or CONFIG_BY_SIZE.get(len(data))
    if not config:
        raise ChameleonError(f"no deduzco config para {len(data)} B; usa --config")
    dev.set_slot(args.slot)
    if not dev.command(f"CONFIG={config}").startswith("1"):
        raise ChameleonError(f"CONFIG={config} rechazado")
    if "XMODEM" not in dev.command("UPLOAD", 0.6).upper():
        raise ChameleonError("UPLOAD no entro en modo XMODEM")
    dev.xmodem_send(data)
    time.sleep(1.0)
    print(f"slot {args.slot}: subidos {len(data)} B, UID={dev.try_query('UID?')}")


def cmd_read_card(dev, args):
    out = args.output or datetime.now().strftime("card-%y%m%d%H%M%S.mfd")
    ok = acr_read_card(out, args.keyfile)
    print(f"{'OK' if ok else 'FALLO'} -> {out}")


def cmd_crack(dev, args):
    out = args.output or datetime.now().strftime("card-%y%m%d%H%M%S.mfd")
    ok = acr_crack(out, args.darkside)
    print(f"{'OK' if ok else 'revisa la salida'} -> {out}")


def cmd_clone(dev, args):
    tmp = datetime.now().strftime("clone-%y%m%d%H%M%S.mfd")
    print("[1/2] leyendo la tarjeta fisica con el ACR122U ...")
    ok = acr_read_card(tmp) or acr_crack(tmp)
    if not ok or not os.path.exists(tmp):
        raise ChameleonError("no pude leer/crackear la tarjeta fisica")
    print(f"[2/2] subiendo {tmp} al slot {args.slot} ...")
    args.file, args.config = tmp, args.config
    cmd_upload(dev, args)


def cmd_detection(dev, args):
    dev.set_slot(args.slot)
    cfg = dev.try_query("CONFIG?")
    if cfg and "DETECTION" not in cfg:
        print(f"aviso: el slot {args.slot} es {cfg}, no un slot de deteccion")
    resp = dev.command("DETECTION", 0.6)
    # el firmware envia bytes crudos tras el estado; los recogemos del buffer
    time.sleep(0.5)
    raw = dev.serial.read(dev.serial.in_waiting or 1)
    out = args.output or f"detection-slot{args.slot}.bin"
    with open(out, "wb") as fh:
        fh.write(raw)
    print(f"datos de deteccion: {len(raw)} B -> {out}")
    mk = find_mfkey32()
    if not mk:
        print("mfkey32 no encontrado; guardo el crudo para procesar manualmente.")
        return
    print(f"(usa {mk} sobre los pares uid/nt/nr/ar del volcado para recuperar claves)")


def cmd_reset(dev, args):
    print(dev.command("RESET").splitlines()[0])


def cmd_dfu(dev, args):
    print("entrando en modo bootloader (DFU); la placa se reenumerara como 03eb:2fe4")
    try:
        dev.command("UPGRADE", 0.3)
    except Exception:
        pass


def build_parser():
    p = argparse.ArgumentParser(description="CLI todo-en-uno para ChameleonMini RevE rebooted")
    p.add_argument("-p", "--port", help="puerto serie (por defecto autodetecta /dev/ttyACM*)")
    p.add_argument("-V", "--version", action="version", version=CURRENT_VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="version + resumen de slots").set_defaults(func=cmd_info)
    sub.add_parser("slots", help="lista los slots").set_defaults(func=cmd_slots)

    s = sub.add_parser("config", help="fija la config de un slot"); s.set_defaults(func=cmd_config)
    s.add_argument("slot", type=int); s.add_argument("config")

    s = sub.add_parser("setuid", help="fija el UID de un slot"); s.set_defaults(func=cmd_setuid)
    s.add_argument("slot", type=int); s.add_argument("hex")

    s = sub.add_parser("atqa", help="fija el ATQA"); s.set_defaults(func=cmd_atqa)
    s.add_argument("slot", type=int); s.add_argument("hex")

    s = sub.add_parser("sak", help="fija el SAK"); s.set_defaults(func=cmd_sak)
    s.add_argument("slot", type=int); s.add_argument("hex")

    s = sub.add_parser("create", help="crea un tag desde cero"); s.set_defaults(func=cmd_create)
    s.add_argument("slot", type=int)
    s.add_argument("--config", default="MF_CLASSIC_1K")
    s.add_argument("--uid"); s.add_argument("--atqa"); s.add_argument("--sak")
    s.add_argument("--data", help="volcado a cargar en el slot")

    s = sub.add_parser("dump", help="vuelca slot(s) a fichero"); s.set_defaults(func=cmd_dump)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--slot", type=int); g.add_argument("--all", action="store_true")
    s.add_argument("-o", "--outdir")

    s = sub.add_parser("upload", help="sube un volcado a un slot"); s.set_defaults(func=cmd_upload)
    s.add_argument("file"); s.add_argument("slot", type=int); s.add_argument("-c", "--config")

    s = sub.add_parser("read-card", help="lee una tarjeta fisica (ACR122U)"); s.set_defaults(func=cmd_read_card)
    s.add_argument("-o", "--output"); s.add_argument("-k", "--keyfile")

    s = sub.add_parser("crack", help="recupera claves de una tarjeta fisica"); s.set_defaults(func=cmd_crack)
    s.add_argument("-o", "--output"); s.add_argument("--darkside", action="store_true")

    s = sub.add_parser("clone", help="lee/crackea una tarjeta y la sube a un slot"); s.set_defaults(func=cmd_clone)
    s.add_argument("slot", type=int); s.add_argument("-c", "--config")

    s = sub.add_parser("detection", help="lee datos de deteccion + mfkey32"); s.set_defaults(func=cmd_detection)
    s.add_argument("slot", type=int); s.add_argument("-o", "--output")

    sub.add_parser("reset", help="reinicia el dispositivo").set_defaults(func=cmd_reset)
    sub.add_parser("dfu", help="entra en modo DFU para flashear").set_defaults(func=cmd_dfu)
    return p


def main():
    args = build_parser().parse_args()
    # read-card/crack no necesitan el device conectado por serie
    host_only = args.cmd in ("read-card", "crack")
    dev = None
    try:
        if not host_only:
            dev = Chameleon(args.port)
        args.func(dev, args)
    except ChameleonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if dev:
            dev.close()


if __name__ == "__main__":
    main()
