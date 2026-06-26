#!/bin/bash
set -euo pipefail

case "$TEST_CASE" in
    "pull-artifact")
        ./pull-artifact.sh
        ;;
    "test-qemu")
        ./test.sh
        ;;
    *)
        echo "Error: Test case '$TEST_CASE' not found!" >&2
        exit 1
        ;;
esac
