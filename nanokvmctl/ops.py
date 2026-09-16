"""Async operations over the extended NanoKVM client.

Power/reset/media primitives map onto the library; the composites are `provision`
(upload a local image over HTTP if needed) and `boot` (arm + reboot the host).
"""

from __future__ import annotations

import asyncio
import os
import sys

from nanokvm.models.common import GpioType

from .client import NanoKVMCtlClient, sanitize_iso_name

# ATX front-panel pulse lengths, in milliseconds.
PRESS_SHORT_MS = 800    # normal power on / ACPI shutdown request
PRESS_LONG_MS = 5000    # forced power off (hold power button)
PRESS_RESET_MS = 800    # reset line pulse


def log(msg: str) -> None:
    """Progress output to stderr so stdout stays machine-parseable."""
    print(msg, file=sys.stderr, flush=True)


async def is_on(client: NanoKVMCtlClient) -> bool:
    return bool((await client.get_gpio()).pwr)


async def _wait_power(client: NanoKVMCtlClient, want: bool, timeout: float, interval: float = 2.0) -> bool:
    waited = 0.0
    while waited < timeout:
        if await is_on(client) == want:
            return True
        await asyncio.sleep(interval)
        waited += interval
    return await is_on(client) == want


# --- power -----------------------------------------------------------------

async def power_status(client: NanoKVMCtlClient) -> str:
    return "on" if (await client.get_gpio()).pwr else "off"


async def power_on(client: NanoKVMCtlClient) -> None:
    if await is_on(client):
        log("host is already on; nothing to do")
        return
    await client.push_button(GpioType.POWER, PRESS_SHORT_MS)


async def power_off(client: NanoKVMCtlClient, force: bool = False) -> None:
    if not await is_on(client):
        log("host is already off; nothing to do")
        return
    await client.push_button(GpioType.POWER, PRESS_LONG_MS if force else PRESS_SHORT_MS)


async def power_reset(client: NanoKVMCtlClient) -> None:
    await client.push_button(GpioType.RESET, PRESS_RESET_MS)


async def power_cycle(client: NanoKVMCtlClient, force: bool = False, settle: float = 30.0) -> None:
    if await is_on(client):
        log("powering off…")
        await client.push_button(GpioType.POWER, PRESS_LONG_MS if force else PRESS_SHORT_MS)
        if not await _wait_power(client, want=False, timeout=settle):
            log("warning: host did not report power-off; continuing anyway")
    log("powering on…")
    await client.push_button(GpioType.POWER, PRESS_SHORT_MS)


# --- virtual media ---------------------------------------------------------

async def media_list(client: NanoKVMCtlClient) -> list[str]:
    return list((await client.get_images()).files)


async def media_mounted(client: NanoKVMCtlClient):
    return await client.get_mounted_image()


async def media_mount(client: NanoKVMCtlClient, file: str, cdrom: bool = False) -> None:
    await client.mount_image(file=file, cdrom=cdrom)


async def media_unmount(client: NanoKVMCtlClient) -> None:
    await client.mount_image(file=None)


async def media_delete(client: NanoKVMCtlClient, file: str) -> None:
    await client.delete_image(file)


# --- provisioning + boot ---------------------------------------------------

def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


async def resolve_existing(client: NanoKVMCtlClient, target: str) -> str:
    """Resolve an on-device target: an absolute path, or a name to match in the image list."""
    if target.startswith("/"):
        return target
    files = list((await client.get_images()).files)
    matches = [f for f in files if target.lower() in _basename(f).lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(
            f"no on-device image matching {target!r}; available: {files or '(none)'}. "
            f"Pass a local file path to upload, or an absolute /data/... path."
        )
    raise SystemExit(f"multiple on-device images match {target!r}: {matches}")


async def upload(client: NanoKVMCtlClient, local_path: str, name: str | None = None) -> str:
    dev = await client.upload_image(local_path, name)
    return dev


async def provision(client: NanoKVMCtlClient, target: str, upload_name: str | None = None) -> str:
    """Return an on-device path to mount. If `target` is a local file, upload it first."""
    if os.path.isfile(target):
        name = sanitize_iso_name(upload_name or target)
        log(f"uploading {target} -> /data/{name} (HTTP POST /api/download/file)")
        dev = await client.upload_image(target, name)
        log(f"upload complete: {dev}")
        return dev
    return await resolve_existing(client, target)


async def set_next(client: NanoKVMCtlClient, target: str, upload_name: str | None = None,
                   cdrom: bool = False) -> str:
    dev = await provision(client, target, upload_name)
    log(f"arming: mounting {dev} (cdrom={cdrom})")
    await client.mount_image(file=dev, cdrom=cdrom)
    return dev


async def boot(client: NanoKVMCtlClient, target: str, upload_name: str | None = None,
               cdrom: bool = False, settle: float = 45.0, unmount: bool = True) -> None:
    dev = await set_next(client, target, upload_name, cdrom=cdrom)
    if await is_on(client):
        log("host is on -> pulsing reset to reboot into the trampoline")
        await client.push_button(GpioType.RESET, PRESS_RESET_MS)
    else:
        log("host is off -> pressing power to boot the trampoline")
        await client.push_button(GpioType.POWER, PRESS_SHORT_MS)
    log(f"waiting {settle:.0f}s for the trampoline to set BootNext and hand off…")
    await asyncio.sleep(settle)
    if unmount:
        log("unmounting trampoline image so later reboots don't loop through it")
        await client.mount_image(file=None)
    else:
        log("leaving image mounted (--no-unmount)")
    log(f"done; host should now be booting the entry armed by {_basename(dev)}")


async def info(client: NanoKVMCtlClient):
    return await client.get_info()
