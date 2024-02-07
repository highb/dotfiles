#!/bin/bash

ORG=$1

if [[ -z "${ORG}" ]]; then
    echo "USAGE: $0 <org>"
    exit 1
fi

gh repo list $ORG --json nameWithOwner -q '.[].nameWithOwner' | xargs -n 1 gh repo clone

