#!/bin/bash

docker build --rm -t dtc-platform-$(hostname):rtk -f Dockerfile.l4t .
