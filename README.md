# Generate FCOS disk image with image-builder - experimentation

## Overview

This work aims to identify the missing pieces required to FCOS disk images using `image-builder-cli`.
We use `image-builder-cli` instead of `bootc-image-builder` because it is the designated successor in the near future.
Adopting the target binary now helps catch issues early and ensures we receive updates first, as `bootc-image-builder` inherits its changes from i-b-c.

This is a logical continuation of the work done in [coreos-assembler PR #4224](https://github.com/coreos/coreos-assembler/pull/4224/), which introduced the ability to use `bootc install to-filesystem` for FCOS image generation.

## Goals

1. Identify gaps between current `image-builder-cli` capabilities and FCOS requirements
2. Document the missing features/stages needed for full FCOS support
3. Propose solutions that can be contributed upstream to `osbuild/images`.

## Usage

```bash
# Add our configuration to base image
TARGET_FCOS_IMAGE=localhost/fcos-with-image-builder
sudo podman build -f Containerfile -t $TARGET_FCOS_IMAGE

# verify the configuration
sudo podman run --rm $TARGET_FCOS_IMAGE bootc install print-configuration | jq

mkdir -p output

alias ibc='sudo podman run --rm --privileged \
           --network=none \
           -v /var/lib/containers/storage:/var/lib/containers/storage \
           -v ./output:/output \
           ghcr.io/osbuild/image-builder-cli:latest'

# this image was generated from https://github.com/coreos/coreos-assembler/pull/4224/
#BUILDER_IMAGE=quay.io/jbtrystramtestimages/cosa:latest
# Get rid of this line below once https://github.com/osbuild/images/pull/2231 is merged, and 
# contained in a new osbuild/images release which is included in i-b-c
# Then uncomment the line above
# Also integrate a build of 
# https://github.com/osbuild/images/pull/2222
BUILDER_IMAGE=quay.io/jbtrystramtestimages/cosa-ib
#sudo podman build -f Containerfile-cosa -t $BUILDER_IMAGE

alias ibc='sudo podman run --rm --privileged --network=none -v /var/lib/containers/storage:/var/lib/containers/storage -v ./output:/output -v ./fcos-bp.toml:/fcos-bp.toml $BUILDER_IMAGE'

# Generate the disk image
ibc build qcow2 \
          --bootc-build-ref $BUILDER_IMAGE \
          --bootc-ref $TARGET_FCOS_IMAGE \
          --output-dir fedora-coreos \
          --output-name fedora-coreos-rawhide \
          --with-buildlog \
          --with-manifest \
          --with-metrics \
          --blueprint /fcos-bp.toml

# Check the osbuild manifest that was generated and used
jq . output/fedora-coreos/fedora-coreos-rawhide.osbuild-manifest.json

# boot the image with cosa
cosa run -c --qemu-image output/fedora-coreos/fedora-coreos-rawhide.qcow2

# run the tests
kola run --qemu-image output/fedora-coreos/fedora-coreos-rawhide.qcow2
```

## Issues

I'm using the issues section to report all the issues as it's more appropriate to discuss.

* [image-builder is missing ignition support](https://github.com/joelcapitao/bib-fcos-experimentation/issues/1)
* [coreos-gpt-setup fails to resize rootfs partition](https://github.com/joelcapitao/bib-fcos-experimentation/issues/2)
* [Support 4k sector size through blueprint](https://github.com/joelcapitao/bib-fcos-experimentation/issues/8)
