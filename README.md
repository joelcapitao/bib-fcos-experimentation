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
├── .github/
│   ├── merge-blueprints.py       # Merges layered blueprints into one (concatenates kernel args)
│   └── workflows/
│       └── check-blueprints.yaml # CI: ensures generated blueprints are up to date
│
├── .tekton/                      # Konflux/Tekton pipeline definitions
│   ├── rawhide-x86-*-{pull-request,push}.yaml
│   └── tasks/
│       └── image-builder.yaml    # Tekton task for image-builder-cli
│
├── blueprints/
│   ├── sources/                  # Source blueprint layers (hand-edited)
│   │   ├── shared/
│   │   │   ├── base.toml         # Common blueprint: image name, ignition firstboot, shared kargs
│   │   │   └── x86_64.toml      # Arch-specific shared kargs (e.g. $ignition_firstboot)
│   │   ├── qemu/                 # One dir per platform
│   │   │   ├── x86_64.toml      # ignition.platform.id + console kargs + grub config
│   │   │   ├── aarch64.toml
│   │   │   └── ...
│   │   ├── metal/
│   │   ├── aws/
│   │   └── ...                   # applehv, azure, gcp, hetzner, ibmcloud, kubevirt,
│   │                             # openstack, oraclecloud, proxmoxve, virtualbox, vmware
│   └── generated/                # Auto-generated merged blueprints (do not edit)
│       ├── qemu-x86_64.toml
│       ├── metal-aarch64.toml
│       └── ...                   # One file per platform-arch combination
│
├── iso/
│   ├── Containerfile             # Derives an FCOS image for generic live ISO builds
│   └── patches/                  # Temporary CoreOS live/dracut compatibility patches
│
├── image-builder-config.yaml     # Builder and CLI image references
└── platforms.yaml                # Canonical console kargs per arch/platform (reference)
```

### Design principles

- **Blueprints are layered** and merged by `.github/merge-blueprints.py`.
  The script deep-merges TOML files in order, with one special rule:
  `customizations.kernel.append` values are **concatenated** (space-separated)
  instead of overridden, so kernel arguments accumulate across layers.
  1. `blueprints/sources/shared/base.toml` — config common to every image (ignition firstboot, name, shared kargs)
  2. `blueprints/sources/shared/<arch>.toml` *(optional)* — arch-specific shared kargs
  3. `blueprints/sources/<platform>/<arch>.toml` — platform ID, console kargs, and grub config

  Future variants (e.g. `debug`) can add a fourth layer.

- Each `<platform>/<arch>.toml` is explicit and self-contained — every arch has
  its own file even when the kargs happen to be identical.

- **`blueprints/generated/`** contains pre-merged blueprints (one per
  platform-arch combination) produced by `merge-blueprints.py --generate-all`.
  These files are committed to the repo and validated by CI — do not edit
  them by hand.

## Usage

```bash
TARGET_FCOS_IMAGE=quay.io/fedora/fedora-coreos:rawhide
BUILDER=quay.io/bootc-devel/fedora-bootc-rawhide-standard

# verify the bootc configuration
sudo podman run --rm $TARGET_FCOS_IMAGE bootc install print-configuration | jq

mkdir -p output

alias ibc='sudo podman run --rm --privileged \
           --network=none \
           -v /var/lib/containers/storage:/var/lib/containers/storage \
           -v ./output:/output \
           -v .:/srv \
           ghcr.io/osbuild/image-builder-cli:latest'

# Regenerate all merged blueprints (sources → generated)
python3 .github/merge-blueprints.py --generate-all

# Or merge specific layers manually:
python3 .github/merge-blueprints.py -o blueprint-merged.toml \
    blueprints/sources/shared/base.toml \
    blueprints/sources/shared/x86_64.toml \
    blueprints/sources/qemu/x86_64.toml

ibc build qcow2 \
          --bootc-build-ref $BUILDER \
          --bootc-ref $TARGET_FCOS_IMAGE \
          --output-dir fedora-coreos \
          --output-name fedora-coreos-rawhide \
          --with-buildlog \
          --with-manifest \
          --with-metrics \
          --blueprint /srv/blueprints/generated/qemu-x86_64.toml

# Boot the image with cosa
cosa run -c --qemu-image output/fedora-coreos/fedora-coreos-rawhide.qcow2

# Run the tests
kola run --qemu-image output/fedora-coreos/fedora-coreos-rawhide.qcow2
```

### Experimental live ISO

The `iso/Containerfile` derives an image-builder ready bootc image from FCOS.
It installs the EFI and ISO build tools required by Image Builder, adds
`dmsquash-live` to the initramfs, provides an FCOS live GRUB entry, and
rebuilds the initramfs.

The resulting generic ISO stores its EROFS root filesystem at `LiveOS/squashfs.img`.

> [!IMPORTANT]
> Generic live ISO support depends on the still-unmerged
> [image-builder PR #2414](https://github.com/osbuild/image-builder/pull/2414/).
> The Image Builder CLI container used by `ibc` must be built from that PR. The
> alias below uses the PR build; do not replace it with the upstream
> `latest` image while the PR remains unmerged.

The Containerfile derives directly from `TARGET_FCOS_IMAGE`, which defaults to
`quay.io/fedora/fedora-coreos:rawhide`. Build the derived image with rootful
Podman because the `ibc` alias mounts rootful container storage into Image
Builder:

```bash
ISO_BOOTC_IMAGE=localhost/fcos-live-iso:latest

alias ibc='sudo podman run --rm --privileged \
           --network=none \
           -v /var/lib/containers/storage:/var/lib/containers/storage \
           -v ./output:/output \
           -v .:/srv \
           quay.io/rchandar/image-builder-fork'

sudo podman build --tag "$ISO_BOOTC_IMAGE" iso/

ibc build generic-iso \
          --bootc-ref "$ISO_BOOTC_IMAGE" \
          --output-dir fedora-coreos \
          --output-name fedora-coreos-rawhide \
          --with-buildlog \
          --with-manifest \
           --bootc-default-fs ext4
```
The ISO is written to
`output/fedora-coreos/fedora-coreos-rawhide.iso`.

The compatibility patches under `iso/patches/` adapt the FCOS
`35coreos-live` dracut module to Image Builder's generic ISO layout:

- `live-generator.patch` lets `dmsquash-live` mount the EROFS sysroot when
  `rd.live.image` is present and sets up the transient `/etc` bind mount.
- `module-setup.patch` creates the live-initramfs marker expected by FCOS.
- `ostree-cmdline.patch` preserves `prepare-root.conf`, where the Containerfile
  disables composefs because it is incompatible with the EROFS live root.

These patches target upstream FCOS files and may need to be rebased when those
files change.

### Adding a new platform

1. Create `blueprints/sources/<platform>/<arch>.toml` for each supported arch.
2. Add the platform name to `_PLATFORM_DIRS` in `.github/merge-blueprints.py`.
3. Regenerate: `python3 .github/merge-blueprints.py --generate-all`
4. Commit both the source and the generated files.

CI (`check-blueprints.yaml`) will fail if generated files are out of date.

### Console karg reference

Console kargs follow the canonical FCOS
[platforms.yaml](https://github.com/coreos/fedora-coreos-config/blob/testing-devel/platforms.yaml).

## Current Issues
