#!/bin/sh
 
for i in `grep -o '\b[a-zA-Z0-9_]\+\.o\b' $1 | sort -u` ; do python3 ~/scripts/parse_map.py $1 $i | grep "Total size" ; done | sort -nk 6
