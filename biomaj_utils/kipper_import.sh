#!/bin/bash

# keydb_import.sh imports fresh fasta data into a new version of a keydb database. 
# Prerequisits: 
#
#   keydb.py (from Galaxy tool "Versioned Data" code) is set up and linked as "keydb"
#   /projects2/ref_databases/versioned/$dbname/master/$dbname.md keydb exists
#
# Args:
#
#   $1 Biomaj relative folder/file location of single .fasta data file to import
#   $2 Path of base keydb data store folder
#   #3 Name of keydb file 

curdate=$(date +"%y-%m-%d")

keydb_folder="$2"

# If database doesn't exist, create it:
if [ ! -f "$keydb_folder/master/$3.md" ]; then 
	echo "Initializing keydb database"
	mkdir "$keydb_folder"
	mkdir "$keydb_folder/master"
	keydb "$keydb_folder/master/$3" -M fasta

	# Nice to have this set up for galaxy Versioned Data tool to consume:
	echo "/$keydb_folder/" > $keydb_folder/pointer.keydb
fi

echo "Remote release: $remoterelease"
regex='^[0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4}$'
if [[ $remoterelease =~ $regex ]]
then
	# Provide remote release id as a date.  Name will be auto incremented integer
   keydb "$keydb_folder/master/$3" -i "$datadir/$dirversion/future_release/$1" -d "$remoterelease" -o.
else
	# Provide remote release id as a string that the version can be named.  Date will be marked today.
   keydb "$keydb_folder/master/$3" -i "$datadir/$dirversion/future_release/$1" -I "$remoterelease" -o.
fi
