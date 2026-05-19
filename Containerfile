FROM quay.io/fedora/fedora-coreos:rawhide

ARG ARCH=x86_64

# TODO get that into overlays.d/10-bootc in f-c-c
COPY shared/00-fcos.toml /usr/lib/bootc/install/00-fcos.toml

# https://github.com/joelcapitao/bib-fcos-experimentation/issues/12
COPY disk/${ARCH}.yaml /usr/lib/image-builder/bootc/disk.yaml
