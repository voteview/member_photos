#!/bin/bash
mogrify -verbose -format jpg -quality 75 -resize "2000x2000>" -path images/bio_guide images/raw/bio_guide/*.*
mogrify -verbose -format jpg -quality 75 -resize "2000x2000>" -path images/wiki images/raw/wiki/*.*
mogrify -verbose -format jpg -quality 75 -resize "2000x2000>" -path images/manual images/raw/manual/*.*

jpegoptim --strip-all -P images/manual/*
jpegoptim --strip-all -P images/wiki/*
jpegoptim --strip-all -P images/bio_guide/*

find images/manual -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;
find images/wiki -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;
find images/bio_guide -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;

