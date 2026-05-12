FROM quay.io/fedora/fedora-coreos:rawhide

# TODO get that into overlays.d/10-bootc in f-c-c
COPY 00-fcos.toml /usr/lib/bootc/install/00-fcos.toml

# https://github.com/joelcapitao/bib-fcos-experimentation/issues/12
COPY disk.yaml /usr/lib/image-builder/bootc/disk.yaml
