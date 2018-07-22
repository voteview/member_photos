#!/bin/bash
mogrify -verbose -format jpg -quality 75 -resize "2000x2000>" -path images/bio_guide images/raw/bio_guide/*.*
mogrify -verbose -format jpg -quality 75 -resize "2000x2000>" -path images/wiki images/raw/wiki/*.*
mogrify -verbose -format jpg -quality 75 -resize "2000x2000>" -path images/manual images/raw/manual/*.*
