# nanokvmctl

A small CLI for remotely controlling a server managed by a **Sipeed NanoKVM**:
ATX power/reset, power-state, virtual media (list/mount/unmount/delete), HTTP image
upload, and a one-shot "arm + reboot into" flow. It's a thin wrapper over
[`puddly/python-nanokvm`](https://github.com/puddly/python-nanokvm), adding the
`POST /api/download/file` multipart upload and an OS-boot orchestration.

Pairs with [`uefi_trampoline`](https://github.com/warmdarksea/uefi_trampoline): build
a trampoline ISO for the OS you want, then `nanokvmctl boot ./trampoline-<os>.iso`
uploads it, mounts it, resets the host into it, and unmounts afterwards.

## Install / run

```sh
nix run github:warmdarksea/nanokvmctl -- --help
# or in a checkout:
nix build .#          # -> result/bin/nanokvmctl
nix develop           # dev shell with nanokvmctl + the nanokvm lib on PATH
```

## Usage

```sh
export NANOKVMCTL_PASSWORD=...        # or you'll be prompted
EP=https://10.217.176.172             # or $NANOKVMCTL_ENDPOINT

nanokvmctl --endpoint $EP --insecure power status
nanokvmctl --endpoint $EP --insecure boot ./trampoline-nixos.iso
#   ^ uploads (as trampoline-nixos.iso), mounts as USB, resets, waits, unmounts

# lower-level verbs:
nanokvmctl ... power on | off [--force] | reset | cycle
nanokvmctl ... upload <local.iso> [--name X.iso]
nanokvmctl ... media list | mounted | mount <path> [--cdrom] | unmount | delete <path>
nanokvmctl ... set-next <local-or-device-image>   # arm only (upload+mount, no reset)
nanokvmctl ... boot <target> [--cdrom] [--settle N] [--no-unmount]
nanokvmctl ... info
```

- `--insecure` is required for the NanoKVM's self-signed cert.
- `boot`/`set-next`/`upload` accept a **local file** (uploaded over HTTP) or an
  on-device `/data/...` path / name substring.
- Uploaded names are forced to the server's rule: `^[A-Za-z0-9._-]+$` ending in
  `.iso` (the server also validates that the payload is a real ISO9660).
- `boot --settle N` waits N seconds after the reset before unmounting (default is
  generous so the firmware has read the media; the trampoline's one-shot `BootNext`
  means there's no loop to race, so erring long is safe).

## Config

- `NANOKVMCTL_ENDPOINT` — default endpoint (else pass `--endpoint`).
- `NANOKVMCTL_USERNAME` — default `admin`.
- `NANOKVMCTL_PASSWORD` — password (else prompted).

## Reaching a socket-only endpoint

If the KVM is reachable only over a unix socket (not TCP), bridge it and target
localhost:

```sh
socat TCP-LISTEN:8443,fork,reuseaddr UNIX-CONNECT:/path/to/kvm.sock &
nanokvmctl --endpoint https://127.0.0.1:8443 --insecure info
```

## Packaging notes

- `nanokvm.nix` packages the library (not in nixpkgs) from its PyPI release; the
  flake wires it into the app via `callPackage ./default.nix { inherit nanokvm; }`.
- `default.nix` takes `nanokvm` as an argument, so a consumer (e.g. nornpkgs) can
  supply its own build of the library.
