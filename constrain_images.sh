#!/bin/bash

# Convert gifs, because smartcrop can't handle them.
mogrify -verbose -format jpg -path images/raw/wiki images/raw/wiki/*.gif
rm images/raw/wiki/*.gif

# Constrain all of the raw files that need constraint
python constrain_images.py

# Optimize
jpegoptim --strip-all -P images/manual/*
jpegoptim --strip-all -P images/wiki/*
jpegoptim --strip-all -P images/bio_guide/*

# JPEGTran
find images/manual -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;
find images/wiki -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;
find images/bio_guide -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;

