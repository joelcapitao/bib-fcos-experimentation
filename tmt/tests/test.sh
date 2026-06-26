#!/bin/bash
set -eEuo pipefail
set -x

source "utils.sh"
trap collect_kola_artifacts ERR

QCOW2_FILE=$(find "${COSA_DIR}" -name "*.qcow2" -print -quit)
if [ -z "${QCOW2_FILE}" ]; then
    echo "ERROR: No qcow2 file found in ${COSA_DIR}" >&2
    exit 1
fi

# Translate host path to container path.
# COSA_DIR is bind-mounted at /srv inside the cosa container.
QCOW2_BASENAME=$(basename "${QCOW2_FILE}")
QCOW2_CONTAINER_PATH="/srv/${QCOW2_BASENAME}"
echo "Using qcow2: ${QCOW2_FILE} (container path: ${QCOW2_CONTAINER_PATH})"

if [ "$TEST_CASE" = "test-qemu" ]; then
    # Basic kola tests (excluding reprovision)
    export KOLA_ID="kola"
    export KOLA_EXTRA_ARGS=(
      --qemu-image "${QCOW2_CONTAINER_PATH}"
      --rerun
      --allow-rerun-success=tags=needs-internet
      --on-warn-failure-exit-77
      --tag='!reprovision'
      --parallel=5
    )
    run_kola
    collect_kola_artifacts

    # Reprovision tests (run separately)
    export KOLA_ID="kola-reprovision"
    export KOLA_EXTRA_ARGS=(
      --qemu-image "${QCOW2_CONTAINER_PATH}"
      --tag=reprovision
    )
    run_kola
    collect_kola_artifacts
fi
