#!/bin/bash

python bio_guide.py --congress 1
python wiki.py --min 1
./manual_wiki_override.sh
./constrain_images.sh
