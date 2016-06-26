#!/bin/bash

base=$1

mir=""

for suf in F B
do
	# $(dirname "$0")/convert.sh $base-$suf.Cu.svg
	python $(dirname "$0")/svg2penGcode.py $mir $base-$suf.Cu.svg
	mir=--mirror 
done