"""nanokvmctl command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os as _os
import sys

from . import ops
from .client import NanoKVMCtlClient

DEFAULT_ENDPOINT = _os.environ.get("NANOKVMCTL_ENDPOINT", "https://10.217.176.172")


def _api_base(endpoint: str) -> str:
    """Normalise a host or base URL to the `.../api/` base the library expects."""
    ep = endpoint.rstrip("/")
    if not ep.endswith("/api"):
        ep = ep + "/api"
    return ep + "/"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nanokvmctl", description="Control a Sipeed NanoKVM.")
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                   help=f"NanoKVM base URL or host (default: {DEFAULT_ENDPOINT})")
    p.add_argument("-u", "--username", default=_os.environ.get("NANOKVMCTL_USERNAME", "admin"),
                   help="login user (default: admin, or $NANOKVMCTL_USERNAME)")
    p.add_argument("-p", "--password", default=_os.environ.get("NANOKVMCTL_PASSWORD"),
                   help="login password (default: $NANOKVMCTL_PASSWORD, else prompt)")
    p.add_argument("--insecure", action="store_true",
                   help="do not verify the TLS certificate (NanoKVM ships a self-signed cert)")

    sub = p.add_subparsers(dest="cmd", required=True)

    power = sub.add_parser("power", help="power control / state")
    psub = power.add_subparsers(dest="pcmd", required=True)
    psub.add_parser("status", help="print on/off")
    psub.add_parser("on", help="power on if off")
    poff = psub.add_parser("off", help="request shutdown (ACPI); --force holds the button")
    poff.add_argument("--force", action="store_true", help="long-press to force power off")
    psub.add_parser("reset", help="pulse the reset line")
    pcyc = psub.add_parser("cycle", help="off then on")
    pcyc.add_argument("--force", action="store_true", help="force the power-off half")

    media = sub.add_parser("media", help="virtual media")
    msub = media.add_subparsers(dest="mcmd", required=True)
    msub.add_parser("list", help="list images available on the device")
    msub.add_parser("mounted", help="show the currently mounted image")
    mmount = msub.add_parser("mount", help="mount an on-device image by path")
    mmount.add_argument("file")
    mmount.add_argument("--cdrom", action="store_true", help="mount as CD-ROM instead of USB disk")
    msub.add_parser("unmount", help="unmount any mounted image")
    mdel = msub.add_parser("delete", help="delete an image from the device")
    mdel.add_argument("file")

    up = sub.add_parser("upload", help="upload a local image to the device over HTTP")
    up.add_argument("local", help="path to a local image file")
    up.add_argument("--name", help="on-device name (forced to a valid [A-Za-z0-9._-].iso)")

    setnext = sub.add_parser("set-next", help="arm: (upload if local, then) mount the image")
    setnext.add_argument("target", help="local image path, on-device /data/... path, or name substring")
    setnext.add_argument("--name", help="on-device name when uploading a local file")
    setnext.add_argument("--cdrom", action="store_true")

    boot = sub.add_parser("boot", help="arm the image and reboot the host into it")
    boot.add_argument("target", help="local image path, on-device /data/... path, or name substring")
    boot.add_argument("--name", help="on-device name when uploading a local file")
    boot.add_argument("--cdrom", action="store_true")
    boot.add_argument("--settle", type=float, default=45.0,
                      help="seconds to wait for the trampoline before unmounting")
    boot.add_argument("--no-unmount", dest="unmount", action="store_false",
                      help="leave the image mounted after booting")

    sub.add_parser("info", help="print device info")
    return p


async def _run(args: argparse.Namespace) -> int:
    password = args.password or getpass.getpass("NanoKVM password: ")
    # request_timeout is generous so multi-MB image uploads don't hit the default 10s.
    async with NanoKVMCtlClient(_api_base(args.endpoint), verify_ssl=not args.insecure,
                                request_timeout=900) as client:
        await client.authenticate(args.username, password)

        if args.cmd == "power":
            if args.pcmd == "status":
                print(await ops.power_status(client))
            elif args.pcmd == "on":
                await ops.power_on(client)
            elif args.pcmd == "off":
                await ops.power_off(client, force=args.force)
            elif args.pcmd == "reset":
                await ops.power_reset(client)
            elif args.pcmd == "cycle":
                await ops.power_cycle(client, force=args.force)

        elif args.cmd == "media":
            if args.mcmd == "list":
                for f in await ops.media_list(client):
                    print(f)
            elif args.mcmd == "mounted":
                m = await ops.media_mounted(client)
                print(m.file or "(none)", f"cdrom={m.cdrom}")
            elif args.mcmd == "mount":
                await ops.media_mount(client, args.file, cdrom=args.cdrom)
            elif args.mcmd == "unmount":
                await ops.media_unmount(client)
            elif args.mcmd == "delete":
                await ops.media_delete(client, args.file)

        elif args.cmd == "upload":
            dev = await ops.upload(client, args.local, args.name)
            print(dev)

        elif args.cmd == "set-next":
            await ops.set_next(client, args.target, args.name, cdrom=args.cdrom)

        elif args.cmd == "boot":
            await ops.boot(client, args.target, args.name, cdrom=args.cdrom,
                           settle=args.settle, unmount=args.unmount)

        elif args.cmd == "info":
            i = await ops.info(client)
            print(f"application: {i.application}")
            print(f"mdns:        {i.mdns}")
            print(f"image:       {i.image}")
            print(f"device_key:  {i.device_key}")
            print(f"ips:         {', '.join(str(ip) for ip in i.ips)}")

    return 0


def main() -> None:
    args = build_parser().parse_args()
    try:
        sys.exit(asyncio.run(_run(args)))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
