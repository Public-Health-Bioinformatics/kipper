#!/bin/bash
echo "Bash script to:"
echo " - clean up current_Bacteria_unaligned.fa"
echo " - convert it into proper fasta format,"
echo "Source is http://rdp.cme.msu.edu/download/current_Bacteria_unaligned.fa.gz"
echo "Damion Dooley, Jan 6, 2015"
echo "Running..."

file_name=$datadir/$dirversion/future_release/$1

# Input data it turns out has TABs in it that formatdb/makeblastdb doesn't like
sed --in-place 's/\t/ /g;' $file_name

