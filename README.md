## Using Command-line Kipper

The basic command-line file versioning solution we have created primarily for fasta data, called **Kipper**, is a key-value data store that keeps track of when particular items are inserted or deleted (updates are deletes followed by inserts).  It can recall versions by date or version id.  It can keep versions in one or more volume files.  It currently only accepts two kinds of text file input : 

* "text": any file where each row is a tab/space delimited key-value record.
* "fasta" database, see http://en.wikipedia.org/wiki/FASTA_format

### **Usage**

Kipper works off of a [data store name].md metadata file, and one or more [data store name]_[volume id] files.  Consequently any Kipper command begins with 

	kipper.py [data store name]

Alone, this will list the available versions found within a Kipper data store.

By default, all output goes to stdout (screen), and no changes to Kipper data store files are made.  Thus by default one sees what would happen if an action were taken, but must take an additional step to affect the data store.  The exception to this is with the -M regenerate metadata command described below. 

To export a version of a kipper data store, pipe the extract output to a file via '> [file name]' or use the '-o' [file name] parameter.

To import a new version of a fasta database into a Kipper data store, provide the '-o' parameter with the full data store file name.

If the "-o" parameter includes a period (e.g. "-o.") rather than a file name, this simply allows Kipper to select the default output file name as appropriate, namely:

	For -i --import or -r --revert actions: an update of the Kipper data store.
	For -e --extract action: a save of output to the version file specified in the [data store name].md metadata file.

As well, when -o parameter is a path, and not a specific filename, then Kipper saves the appropriate output file name into the given folder.  This is convenient for extracting versions into separate folders.


List versions of dbFile key/value pairs (by date/time): -l --list (optional)

	kipper.py [data store file]
	kipper.py cpn60 -l

Initialize metadata file and kipper file: -M --rebuild

	kipper.py [data store file] -M [type of database:text|fasta]
	kipper.py cpn60 -M fasta
    
View metadata (json) file: -m --metadata

	kipper.py [data store file] -m
	kipper.py cpn60 -m

Import key/value inserts/deletes based on import file (current date used):  -i --import

	kipper.py [data store file] -i [import file] -o.

Outputs new master database to stdout; doesn't rewrite it.

	kipper.py cpn60 -i sequences.fasta  

Rewrites cpn60 with new version added.

	kipper.py cpn60 -i sequences.fasta -o.

Add Volume to data store (creates new volume file that receives future imports): -V --volume

	kipper.py [data store file] -V -o. 

Rewrites cpn60 with new volume, and new version added to that volume.

	kipper.py cpn60 -V -i sequences.fasta -o.

Extract a version of the file based on given date/time: -e --extract

	kipper.py [data store file] -e -d datetime -o [output file]

Extract a version of the file based on given version Id

	kipper.py [data store file] -e -n [version id] -o [output file]

Have database revert to previous version.  Drops future records, unmarks corresponding deletes:  -r --revert

	kipper.py [data store file] -r -d datetime -o [output file]


Return version of the kipper code:	 -v --version 

	kipper.py -v

### **Options**

-h, --help
	
	Show this help message and exit
  
-M INITIALIZE, --rebuild=INITIALIZE
  
	(Re)generate metadata file [name of db].md . Provide the type of db [text|fasta| etc.]
	
-i DB_IMPORT_FILE_PATH, --import=DB_IMPORT_FILE_PATH
  
	Import key/value inserts/deletes based on delta comparison with import file

-e, --extract	

	Extract a version of the file based on given date/time

-r, --revert

	Have database revert to previous version (-d date/time required).  Drops future records, unmarks corresponding deletes.
	
-m, --metadata
	  
	View metadata file [name of db].md
	  
-l, --list
  
	List versions of dbFile key/value pairs (by date/time)

-v, --version

	Return version of kipper.py code.
  
-o DB_OUTPUT_FILE_PATH, --output=DB_OUTPUT_FILE_PATH
	  
	Output to this file.  Default is to stdio
  
-d DATETIME, --date=DATETIME
  
	Provide date/time for sync, extract or revert operations.  Defaults to now.

-u UNIXTIME, --unixTime=UNIXTIME

	Provide Unix time (integer) for sync, extract or revert operations.

-n VERSION_ID, --number=VERSION_ID
  
	Provide a version id to extract or revert to.

### **Performance**

Kipper has virtually no memory requirements, regardless of the size of input files.  Since fasta databases are mainly just inserts over time, a Kipper data store having many versions usually ends up being modestly larger than the most recent fasta database version size.  Its version extraction speed is linear to the time it take to read and write the archive file.

Currently we are experimenting with reading compressed files and writing compressed volume files, to see which archiving format is best.

### **Example Database**

This repo contains a 'RDB_database_load_v10_8-v11_3.sh' script which downloads and imports the RDP RNA database (https://rdp.cme.msu.edu/) versions 10.18 to 11.3 into a kipper data store.  This takes a few hours to download and process.  The end result is 18 versions of the RDB database that fit into two kipper volumes.  The script needs wget and gunzip, and needs a symlink from say '/usr/local/bin/kipper' to the 'kipper.py' executable.


### **Notes**

A change last year in NCBI's coding of alternate descriptions for a fasta sequence has impact on kipper data store file sizes for archives that span that date. It looks like NCBI converted all records last year to get away from the CTRL-A delimiter for alternate fasta descriptions, which now simply includes origina chevron.  There aren't any CTRL-A characters any more in incoming nt.fasta or nr.fasta files.  Instead one can expect to see    
```
1       3       gi|74|emb|CAA39971.1|   annexin I [Bos taurus]^Agi|264182|gb|AAB25084.1| annexin ...
3               gi|74|emb|CAA39971.1|   annexin I [Bos taurus] >gi|264182|gb|AAB25084.1| annexin ...
```
