#!/bin/bash
echo "Bash script to:"
echo " - download 16S RDP database versions from the Ribosomal Database Project at http://rdp.cme.msu.edu/"
echo " - convert each one into proper fasta format,"
echo " - add it to the keydb versioned data store"
echo "There are three sections to this because of changes in version file naming."
echo "Damion Dooley, Oct 28, 2014"
echo "Running..."

base="10"
urlpref="http://rdp.cme.msu.edu/download/release"
underscore="_"
urlsuf="_unaligned.fa.gz"
ver="_v"

db_name="rdp_rna"

rm -f master/$db_name*
kipper.py master/$db_name -M fasta

for i in {18..29};
do
	addr=$urlpref$base$underscore$i$urlsuf
	target=$db_name$ver$base.$i.fasta
	wget $addr -O $target.gz
        modified="$(date -r $target.gz)"
	gunzip $target.gz
	touch -d "$modified" $target
	# Submit as new version to Kipper; Kipper controls sorting.
	kipper.py master/$db_name -i $target -o . -I "$base.$i"
	rm $target
done

kipper.py master/$db_name -V -o .


for i in {30..32};
do
  	addr=$urlpref$base$underscore$i$urlsuf
    target=$db_name$ver$base.$i.fasta
    wget $addr -O $target.gz
    modified="$(date -r $target.gz)"
    gunzip $target.gz
    touch -d "$modified" $target
    kipper.py master/$db_name -i $target -o . -I "$base.$i"
    rm $target
done


base="11"
urlsuf="_Bacteria_unaligned.fa.gz"

for i in {1..3};
do
  	addr=$urlpref$base$underscore$i$urlsuf
    target=$db_name$ver$base.$i.fasta
    wget $addr -O $target.gz
    modified="$(date -r $target.gz)"
    gunzip $target.gz
    touch -d "$modified" $target
    kipper.py master/$db_name -i $target -o . -I "$base.$i"
    rm $target

done

