#!/bin/bash

# Convert gifs, because smartcrop can't handle them.
mogrify -verbose -format jpg -path images/raw/wiki images/raw/wiki/*.gif
rm images/raw/wiki/*.gif

# Constrain all of the raw files that need constraint
python constrain_images.py
