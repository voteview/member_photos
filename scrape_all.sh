#!/bin/bash

mkdir images
mkdir images/wiki
mkdir images/bio_guide
mkdir images/manual
mkdir images/raw
mkdir images/raw/bio_guide
mkdir images/raw/wiki
mkdir images/raw/manual

python bio_guide.py --min 1
python wiki.py --min 1
./manual_wiki_override.sh
./constrain_images.sh
