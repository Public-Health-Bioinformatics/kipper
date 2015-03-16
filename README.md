## Using Command-line Kipper

The basic command-line file versioning solution we have created primarily for fasta data, called **Kipper**, is a key-value data store that keeps track of when particular items are inserted or deleted (updates are deletes followed by inserts).  It can recall versions by date or version id.  It can keep versions in one or more volume files.  It currently only accepts two kinds of text file input : 

* "text": any file where each row is a tab/space delimited key-value record.
* "fasta" database.

### **Usage**
 
By default, all outputs go to stdout and affect no change in Kipper database files unless the '-o' parameter is supplied.  Thus by default one sees what would happen if an action were taken, but must take an additional step to affect the data store.  The exception to this is with the -M regenerate metadata command described below. 

If you include a period in the "-o ." parameter, rather than a file name, this simply allows Kipper to select the output file name as appropriate, namely:

**"-o ." is a special parameter that leads to:**
   **an update of the .kipper database for --import or --revert actions**
   **a save of output to file specified in the data store's .md metadata file for -e --extract action**

As well, when -o parameter is a path, and not a specific filename, then kipper.py looks up what the appropriate output file name is according to the metadata file.


List versions of dbFile key/value pairs (by date/time): -l --list (optional)

	kipper.py [database file]
	kipper.py cpn60 -l

Initialize metadata file and kipper file: -M --rebuild

    kipper.py [database file] -M [type of database:text|fasta]
	kipper.py cpn60 -M fasta
    
View metadata (json) file:  -m --metadata

	kipper.py [database file] -m
	kipper.py cpn60 -m	

Import key/value inserts/deletes based on import file (current date used):  -i --import

	kipper.py [database file] -i [import file] -o.

Outputs new master database to stdout; doesn't rewrite it.

	kipper.py cpn60 -i sequences.fasta   

Rewrites cpn60 with new version added.

	kipper.py cpn60 -i sequences.fasta -o. 

Add Volume to database (creates new volume file that receives future imports): -V --volume

	kipper.py [database file] -V -o. 

Rewrites cpn60 with new volume, and new version added to that volume.

	kipper.py cpn60 -V -i sequences.fasta -o. 

Extract a version of the file based on given date/time: -e --extract

	kipper.py [database file] -e -d datetime -o [output file]

Extract a version of the file based on given version Id

	kipper.py [database file] -e -n [version id] -o [output file]

Have database revert to previous version.  Drops future records, unmarks corresponding deletes:  -r --revert

	kipper.py [database file] -r -d datetime -o [output file]


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
  
-c, --check

	Test an input file.  Provide the file name and path.

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

Currently we are experimenting with reading compressed files and writing compressed volume files, to see which solution is fastest.
