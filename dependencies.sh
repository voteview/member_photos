#!/bin/bash

if [ "$(uname)" == "Darwin" ]; then
	echo "Mac detected -- using brew to install dependencies."
	brew install jpegoptim imagemagick node jpeg
	npm install -g opencv
	npm install -g smartcrop-cli
else
	echo "Non-mac detected -- using apt to install dependencies."
	apt-get install jpegoptim libjpeg-progs imagemagick libopencv-dev nodejs
	npm install -g opencv
	npm install -g smartcrop-cli
fi
