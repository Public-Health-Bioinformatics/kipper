#!/bin/bash
echo "Bash script to:"
echo " - Convert cpn60 database into proper fasta format."
echo "Source is http://haruspex.usask.ca/cpnDB/cpn60_a_nut"
echo "Damion Dooley, Dec 19, 2014"
echo "Running..."

file_name=$datadir/$dirversion/future_release/$1

# All entries with >v are preliminary / not valid yet. 
sed --in-place '/^>v/Q' $file_name

# Switch b[cpndb id] [accession id] line around to match fasta header
sed -r --in-place 's/>(b[0-9]+) ([a-zA-Z0-9_\.]+) (.*)/>ref|\2|\1 \3/g;' $file_name
