#!/bin/bash
echo "Bash script to:"
echo " - test extract 16S RDP database versions 10.18 - 11.3 from local Kipper data store"
echo "Damion Dooley, April 23, 2015"
echo "Running..."

db_name="rdp_rna"
db_folder="master_test"

for i in {1..18};
do
	
	# Extract each version from Kipper data store by version id (rather than version label)
	python analyze.py "version $i" kipper $db_folder/$db_name -e -n$i -o .

done

