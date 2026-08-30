#!/bin/bash

for repo in `ls -d */`; do
	pushd $repo
	git pull
	popd
done
