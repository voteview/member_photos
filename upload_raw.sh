#!/bin/bash

cd images
aws s3 cp raw s3://voteview_ucla/images_raw --recursive
