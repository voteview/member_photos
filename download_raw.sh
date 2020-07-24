#!/bin/bash

cd images
aws s3 cp s3://voteview-ucla/images_raw raw --recursive
