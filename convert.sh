#!/bin/bash

filename=`basename $1`
ext=${filename##*.}

if [[ $ext != "svg" ]]
then
	echo "Should be svg file. $ext provided"
	exit 1 
fi 

case $1 in
  /*) absolutePath=$1;;
  *) absolutePath=$PWD/$1;;
esac

inkscape -z -f "$absolutePath" -d 600 -y 1.0 -e "$absolutePath.png"
convert "$absolutePath.png" "$absolutePath.pnm"
potrace -s -r 600 -o "$absolutePath.svg" "$absolutePath.pnm"
rm "$absolutePath.png" "$absolutePath.pnm"
