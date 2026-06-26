#!/bin/bash
set -eEuo pipefail
set -x

export COREOS_ASSEMBLER_CONTAINER_LATEST="quay.io/coreos-assembler/coreos-assembler:latest"
export COSA_DIR="$HOME/workspace/build"

cosa() {
    podman run --rm --security-opt=label=disable --privileged \
      -v "${COSA_DIR}:/srv" --device=/dev/kvm \
      --device=/dev/fuse --tmpfs=/tmp -v /var/tmp:/var/tmp \
      --name=cosa "${COREOS_ASSEMBLER_CONTAINER_LATEST}" "$@"
}

collect_kola_artifacts() {
    mkdir -p "$TMT_TEST_DATA"
    cd "${COSA_DIR}" && \
      tar -C "${OUTPUT_DIR}" -c --xz "${KOLA_ID}" > "${KOLA_ID}-${TOKEN}.tar.xz"
    cd "${COSA_DIR}" && \
      mv "${KOLA_ID}-${TOKEN}.tar.xz" "${TMT_TEST_DATA}/${KOLA_ID}-${TOKEN}.tar.xz"
}

run_kola() {
    # Create output directory on the host; cosa sees it under /srv/
    OUTPUT_DIR=$(mktemp -d "${COSA_DIR}/tmp/kola-XXXX")
    OUTPUT_DIR_BASENAME=$(basename "${OUTPUT_DIR}")
    TOKEN="$(uuidgen | cut -f1 -d -)"
    KOLA_ID="${KOLA_ID:-kola}"
    cosa kola run --arch="$(arch)" \
      --output-dir="/srv/tmp/${OUTPUT_DIR_BASENAME}/${KOLA_ID}" \
      "${KOLA_EXTRA_ARGS[@]}"
}
