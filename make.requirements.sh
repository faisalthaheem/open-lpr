#!/bin/sh
pip3 install pipreqs
pipreqs --force ./shared
pipreqs --force ./ftp
pipreqs --force ./platedetector
pipreqs --force ./plateclassifier
pipreqs --force ./ocr
