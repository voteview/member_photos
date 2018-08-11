#!/bin/bash

# Nuke all the current output files
rm images/bio_guide/*.*
rm images/wiki/*.*
rm images/manual/*.*

# Convert gifs, because smartcrop can't handle them.
mogrify -verbose -format jpg -path images/raw/wiki images/raw/wiki/*.gif
rm images/raw/wiki/*.gif

# Loop over new files.
for filename in images/raw/{wiki,manual}/*
do
  # Get basic info on the file.
  aspect=$(identify -format '%[fx:w/h]' "$filename")
  width=$(identify -format '%[fx:w]' "$filename")
  height=$(identify -format '%[fx:h]' "$filename")
  outpath=$(echo "$filename" | rev | cut -d"/" -f2 | rev)
  strip_path=$(basename $filename)
  new_filename=${strip_path%%.*}
  extension=${strip_path##*.}

  # Check to see if we should do a standard mogrify or a smart crop.
  if (( $(echo "$aspect > 0.85" | bc -l) || $(echo "$aspect < 0.75" | bc -l) ))
  then
    # Get the new dimensions post-crop
    if [[ width -gt height ]]
    then
      new_height=$height
      new_width=$(($height*4/5))
    else
      new_width=$width
      new_height=$(($width*5/4))
    fi

    # New dimensions are too big, shrink to max.
    if [[ new_height -gt 600 ]]
    then
      new_height=600
      new_width=480
    fi


    # Do the smart crop.
    smartcrop --width $new_width --height $new_height --faceDetection $filename --outputFormat jpg --quality 80 images/${outpath}/${new_filename}.jpg
    echo "$filename has bad aspect ratio, correct to $new_width x $new_height and output to $new_filename.jpg"
  else
    # Do standard mogrify
    mogrify -verbose -format jpg -quality 75 -resize "600x600>" -path images/${outpath} $filename
    echo "$filename ok shrink with mogrify."
  fi
done

# Mogrify bio_guide photos
mogrify -verbose -format jpg -quality 75 -resize "600x600>" -path images/bio_guide images/raw/bio_guide/*.*

# Optimize
jpegoptim --strip-all -P images/manual/*
jpegoptim --strip-all -P images/wiki/*
jpegoptim --strip-all -P images/bio_guide/*

# JPEGTran
find images/manual -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;
find images/wiki -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;
find images/bio_guide -name "*.jpg" -type f -exec jpegtran -copy none -optimize -outfile {} {} \;

