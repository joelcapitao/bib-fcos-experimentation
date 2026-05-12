# image-builder pipelines for FCOS

## Overview

This work aims iterate on a bootimages definitions repo for Fedora CoreOS, to be used by image builder through Konflux.

## Goals

1. Setup a clean directory structure to define and maintain all our produced artifacts
2. Develop and iterate on a image-builder tekton task for Konflux.
3. Identify what can be contributed to image-builder for shared maintenance between FCOS and image-builder.

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
           -v ./fcos-bp.toml:/fcos-bp.toml \
           ghcr.io/osbuild/image-builder-cli:latest'

# We use the bootc base image as the builder image as it
# comes with python and is generally versionned closely with FCOS.
BUILDER=quay.io/bootc-devel/fedora-bootc-rawhide-standard

# Generate the disk image
ibc build qcow2 \
          --bootc-build-ref $BUILDER \
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

