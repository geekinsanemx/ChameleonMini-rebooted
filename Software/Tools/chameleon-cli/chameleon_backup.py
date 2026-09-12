#!/usr/bin/env python3
"""
chameleon_backup.py - Backup y restore de slots del ChameleonMini.

A diferencia de un simple volcado de datos, guarda el ESTADO COMPLETO de cada
slot: configuracion, UID, ATQA, SAK, memsize y el contenido de memoria. El
restore reconstruye el slot tal cual estaba.

Uso:
    # respaldar
    chameleon_backup.py backup --all [-o DIR]
    chameleon_backup.py backup --slot N [-o DIR]

    # restaurar
    chameleon_backup.py restore --all DIR
    chameleon_backup.py restore --slot N DIR

Formato de backup (un directorio):
    manifest.json          estado de cada slot
    slotN.bin              datos de memoria de cada slot (si aplica)

CHANGELOG
  1.0.0 - Version inicial.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

from chameleon import Chameleon, ChameleonError, CONFIG_BY_SIZE

CURRENT_VERSION = "1.0.0"
CLOSED = ("CLOSED", "NO CONFIGURATION", "NONE", "", None)


def backup_slot(dev, n, outdir):
    info = dev.slot_info(n)
    entry = {
        "slot": n,
        "config": info["config"],
        "uid": info["uid"],
        "memsize": info["memsize"],
        "atqa": dev.try_query("ATQA?"),
        "sak": dev.try_query("SAK?"),
        "data_file": None,
    }
    if info["config"] not in CLOSED:
        if "XMODEM" in dev.command("DOWNLOAD", 0.6).upper():
            blob = dev.xmodem_receive()
            memsize = int(info["memsize"]) if (info["memsize"] or "").isdigit() else len(blob)
            fname = f"slot{n}.bin"
            with open(os.path.join(outdir, fname), "wb") as fh:
                fh.write(blob[:memsize] if memsize <= len(blob) else blob)
            entry["data_file"] = fname
    return entry


def do_backup(dev, args):
    outdir = args.outdir or datetime.now().strftime("backup-%y%m%d%H%M%S")
    os.makedirs(outdir, exist_ok=True)
    orig = dev.active_slot()
    slots = range(8) if args.all else [args.slot]
    manifest = {"firmware": dev.try_query("VERSION?"),
                "created": datetime.now().isoformat(timespec="seconds"),
                "slots": []}
    for n in slots:
        e = backup_slot(dev, n, outdir)
        manifest["slots"].append(e)
        print(f"slot {n}: config={e['config']} uid={e['uid']} "
              f"{'datos '+e['data_file'] if e['data_file'] else '(sin datos)'}")
    dev.set_slot(orig)
    with open(os.path.join(outdir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"backup en: {outdir}")


def restore_slot(dev, entry, srcdir):
    n = entry["slot"]
    dev.set_slot(n)
    cfg = entry["config"]
    if cfg in CLOSED:
        dev.command("CLEAR")  # el rebooted vacia el slot activo con CLEAR (no CONFIG=NONE)
        return f"slot {n}: CLOSED"
    if not dev.command(f"CONFIG={cfg}").startswith("1"):
        return f"slot {n}: CONFIG={cfg} RECHAZADO"
    # datos primero (fija el UID embebido), luego sobrescribimos campos sueltos
    if entry.get("data_file"):
        path = os.path.join(srcdir, entry["data_file"])
        with open(path, "rb") as fh:
            data = fh.read()
        if "XMODEM" in dev.command("UPLOAD", 0.6).upper():
            dev.xmodem_send(data)
            time.sleep(1.0)
    if entry.get("uid"):
        dev.command(f"UID={entry['uid']}")
    if entry.get("atqa"):
        dev.command(f"ATQA={entry['atqa']}")
    if entry.get("sak"):
        dev.command(f"SAK={entry['sak']}")
    return (f"slot {n}: config={dev.try_query('CONFIG?')} uid={dev.try_query('UID?')}")


def do_restore(dev, args):
    srcdir = args.dir
    with open(os.path.join(srcdir, "manifest.json")) as fh:
        manifest = json.load(fh)
    orig = dev.active_slot()
    fw = dev.try_query("VERSION?")
    if manifest.get("firmware") and fw and manifest["firmware"].split()[0] != fw.split()[0]:
        print(f"aviso: backup de '{manifest['firmware']}' -> dispositivo '{fw}'")
    entries = manifest["slots"]
    if not args.all:
        entries = [e for e in entries if e["slot"] == args.slot]
        if not entries:
            raise ChameleonError(f"el backup no contiene el slot {args.slot}")
    for e in entries:
        print(restore_slot(dev, e, srcdir))
    dev.set_slot(orig)
    print("restore completado")


def build_parser():
    p = argparse.ArgumentParser(description="Backup y restore de slots del ChameleonMini")
    p.add_argument("-p", "--port")
    p.add_argument("-V", "--version", action="version", version=CURRENT_VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backup", help="respalda slots a un directorio")
    b.set_defaults(func=do_backup)
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true"); g.add_argument("--slot", type=int)
    b.add_argument("-o", "--outdir")

    r = sub.add_parser("restore", help="restaura slots desde un directorio")
    r.set_defaults(func=do_restore)
    r.add_argument("dir")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true"); g.add_argument("--slot", type=int)
    return p


def main():
    args = build_parser().parse_args()
    dev = None
    try:
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
