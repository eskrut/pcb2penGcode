#!/bin/bash

base=$1

mir=""

for suf in F B
do
	python $(dirname "$0")/svg2penGcode.py --merge-tracks $mir $base-$suf.Cu.svg
	mir=--mirror 
done