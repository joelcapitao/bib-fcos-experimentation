#!/bin/bash
set -eEuo pipefail
set -x

source "utils.sh"

if [ -z "${IMAGE_URL:-}" ]; then
    echo "ERROR: IMAGE_URL is not set. Provide the OCI image reference." >&2
    echo "  e.g. IMAGE_URL=quay.io/konflux-fedora/coreos-tenant/disk-images-rawhide:on-pr-<revision>" >&2
    exit 1
fi

echo "=== Pulling QEMU artifact from OCI index ==="
echo "IMAGE_URL: ${IMAGE_URL}"

mkdir -p "${COSA_DIR}"

# Pull the qcow2 from the OCI index using platform selector.
# The OCI index uses os=<artifact> and architecture=<arch> as platform
# metadata, so --platform qemu/amd64 selects the QEMU disk image for x86_64.
oras pull --output "${COSA_DIR}" --platform "qemu/amd64" "${IMAGE_URL}"

QCOW2_FILE=$(find "${COSA_DIR}" -name "*.qcow2" -print -quit)
if [ -z "${QCOW2_FILE}" ]; then
    echo "ERROR: No qcow2 file found after oras pull" >&2
    ls -lhR "${COSA_DIR}"
    exit 1
fi

echo "=== Successfully pulled: ${QCOW2_FILE} ==="
ls -lh "${QCOW2_FILE}"
