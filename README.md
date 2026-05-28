# Generate FCOS disk image with image-builder - experimentation

## Overview

This work aims to identify the missing pieces required to FCOS disk images using `image-builder-cli`.
We use `image-builder-cli` instead of `bootc-image-builder` because it is the designated successor in the near future.
Adopting the target binary now helps catch issues early and ensures we receive updates first, as `bootc-image-builder` inherits its changes from i-b-c.

This is a logical continuation of the work done in [coreos-assembler PR #4224](https://github.com/coreos/coreos-assembler/pull/4224/),
which introduced the ability to use `bootc install to-filesystem` for FCOS image generation.

## Goals

 1. Identify gaps between current `image-builder-cli` capabilities and FCOS requirements
 2. Document the missing features/stages needed for full FCOS support
 3. Propose solutions that can be contributed upstream to `osbuild/images`.
 4. Develop and iterate on an image-builder Tekton task for Konflux.
 5. Develop an automated workflow with Konflux and its facilities

## Requirements

 1. We aim to not define any custom tekton task and use only upstream vetted tasks.
    We treat konflux as a black-box that we don't own, in order to conform with coforma-compliance
    policies.

## Repository structure

```
.
├── shared/
│   ├── blueprint.toml   # Common blueprint: image name + ignition firstboot marker
│   └── 00-fcos.toml     # bootc install config: stateroot, mount specs, fs type
│
├── disk/
│   ├── x86_64.yaml      # GPT layout: BIOS-BOOT + EFI + boot + root
│   ├── aarch64.yaml     # GPT layout: reserved + EFI + boot + root
│   ├── ppc64le.yaml     # GPT layout: PReP + reserved + boot + root
│   └── s390x.yaml       # GPT layout: boot (p3) + root (p4)
│
├── qemu/                # Artifact: qcow2 image for QEMU
│   ├── x86_64.toml      # ignition.platform.id=qemu + tty0/ttyS0 console
│   ├── aarch64.toml     # ignition.platform.id=qemu
│   ├── ppc64le.toml     # ignition.platform.id=qemu + hvc0/tty0 console
│   └── s390x.toml       # ignition.platform.id=qemu
│
└── metal/               # Artifact: raw image for bare metal
    ├── x86_64.toml      # ignition.platform.id=metal
    ├── aarch64.toml     # ignition.platform.id=metal
    ├── ppc64le.toml     # ignition.platform.id=metal
    └── s390x.toml       # ignition.platform.id=metal
```

### Design principles

- **`disk/`** is the single source of truth for partition tables, one file per
  architecture. The partition table is never duplicated.

- **Blueprints are layered** and merged by image-builder-cli at build time:
  1. `shared/blueprint.toml` — config common to every image (ignition firstboot, name)
  2. `<artifact>/<arch>.toml` — platform ID and arch-specific console kargs

  Future variants (e.g. `debug`) add a third layer by placing a
  `<artifact>/<arch>/<variant>.toml` with only the extra kargs.

- Each `<artifact>/<arch>.toml` is explicit and self-contained — every arch has
  its own file even when the kargs happen to be identical.

- The `shared/00-fcos.toml` file is a bootc install configuration that must be
  present inside the target container image at
  `/usr/lib/bootc/install/00-fcos.toml`. This is tracked here for reference
  and will eventually be upstreamed into `fedora-coreos-config` overlays.d.

## Usage

```bash
TARGET_FCOS_IMAGE=localhost/fcos-with-image-builder
BUILDER=quay.io/bootc-devel/fedora-bootc-rawhide-standard

# Build the FCOS image
sudo podman build -f Containerfile -t $TARGET_FCOS_IMAGE

# verify the bootc configuration
sudo podman run --rm $TARGET_FCOS_IMAGE bootc install print-configuration | jq

mkdir -p output

alias ibc='sudo podman run --rm --privileged \
           --network=none \
           -v /var/lib/containers/storage:/var/lib/containers/storage \
           -v ./output:/output \
           -v .:/srv \
           ghcr.io/osbuild/image-builder-cli:latest'

# Build a specific (artifact, arch, variant) combination.
# Blueprints are merged in order: shared → artifact/arch → variant (if any).
#
# Example: qemu image for x86_64, base variant
ibc build qcow2 \
          --bootc-build-ref $BUILDER \
          --bootc-ref $TARGET_FCOS_IMAGE \
          --output-dir fedora-coreos \
          --output-name fedora-coreos-rawhide \
          --with-buildlog \
          --with-manifest \
          --with-metrics \
          --blueprint /srv/shared/blueprint.toml \
          --blueprint /srv/qemu/x86_64.toml

# Boot the image with cosa
cosa run -c --qemu-image output/fedora-coreos/fedora-coreos-rawhide.qcow2

# Run the tests
kola run --qemu-image output/fedora-coreos/fedora-coreos-rawhide.qcow2
```

### Adding a new variant

Create `<artifact>/<arch>/<variant>.toml` with only the extra kargs:

```toml
# Example: qemu/x86_64/debug.toml
[customizations.kernel]
append = "systemd.log_level=debug"
```

Then pass it as a third `--blueprint` flag after the arch-level one.

### Console karg reference

Console kargs follow the canonical FCOS
[platforms.yaml](https://github.com/coreos/fedora-coreos-config/blob/testing-devel/platforms.yaml).

## Current Issues

