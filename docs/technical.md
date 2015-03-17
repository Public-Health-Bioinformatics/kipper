## Kipper Data Store Format

A Kipper key-value data store consists of one or more master database volume files:

    [db name]._1
    [db name]._2

etc.

and usually a metadata file:

    [db name].md

A volume file contains a range of versions starting with a complete version file that subsequent versions diff off of.  The reason for having separate volumes is that sometimes there can be a substantial change to all the entries in a database; as well by having a database broken into volumes, extraction for a particular volume doesn't have to involve a file that is much larger than the extracted version.

The metadata file contains a json data serialization of the following fields.

Items in *italics* are not currently implemented.

###Metadata File .md
| field | required | description
| -------|----------|-------------
| compression | | Currently only ".gz" option supported.  Enables kipper volume files to be compressed.  Reads and writes them via streaming.
| version | yes | Kipper data format version (taken from kipper.py software version used to create this metadata file - assuming it can manage the master data file that it is generating the metadata file for.)
| name	| | Name of this versioned database, file or data collection
| type	| | Content type (user defined, e.g. "fasta" )
| [curation fields] | | ???
| description | |	
| *processor*	| | *python or other executable to run before importing given input file into kipper or after extracting data from kipper.  I.e. handles the extra steps required to import or produce type of data indicated above.  It specifies the transformation from input to 1 line key-value record, and the sort function used to order the records.*
| *hash* | | *Hash of entire latest master file content that this pertains to; enables verification that this metadata file applies to a given kipper master file.* 
| volumes | yes | Table of volumes (see below).  Each volume contains a range of versions, starting with a complete version file that subsequent versions diff off of.
 | | | 

### Volume
| field | required | description |
|-------|----------|-------------|
|floor_id | yes | Lowest version id that this volume pertains to.  It covers this id and all up to next volume's floor_id |
| versions | yes | Table of versions (see below)|
| *prefixes* | *no* | *... keep track of the rows and hash of each prefix file?* |
 | | | 
 
### Version
 
| field | description |
| ----- | ------------- |
| id | Internal to kipper, increments from 1
| name | Optional. Version label, can be any alphanumeric string with spaces, dots and underscores.  We recommend it be formatted as "[YYYY/MM/DD] [HH:MM] v[version number]"
| file_name | name of imported file. 
| created | Publisher's date/time of creation (initially taken from modified date of imported file)
| file_size | Import file size - bytes, uncompressed.  Note output file size may be less since whitespace is trimmed from around various fields, and sequence output is split into 80 character lines..
| *hash* | *Hash of raw input version file contents before preprocessing. This facilitates checking of a local file (or online data source if it includes a separate hash file) to see if a master file already contains it.*
| rows | Count total key-value transaction rows
| inserts | Count of rows that are inserts
| updates | count of rows that are updates (not implemented)
| deletes | Count of rows that are deletes
| keys | Count of unique keys
| |

The metadata file is not essential insofar as most of the information it contains (except for version creation date and some input file details) can be regenerated from the kipper file (using the command line "-M" parameter).  

In a volume each line of data contains 1 key-value record transaction, either an insert or delete.  They are sorted so that we know when reading through the file whether the current key-value pair needs to be inserted/updated/deleted in the master file.  The particular sorting algorithm doesn't really matter as long as it is consistent (sorting "A..." before "a..." one time but then reversing them the next time is bad!).

A kipper key-value record consists of:

 | creation version id | deletion version id | key (text) | value (text) |
 | ---------------------- | ---------------------- | ----------- | -------------- |

e.g.

	    1       11      S000000080      Clostridium indolis; DSM 755; Y18184        cctggctcaggatgaacgctggcggcgtgcttaacacatgcaagtcgagcgaagcgatttaaatgaagttttcggatggaatttaaattgact ...

When the same key has multiple version ids, the first is the creation version, and subsequent ones are updates (delete/create together), followed possibly by a final delete.

### Kipper prefix files
**In the future** we will have a provision for the master database volume file to be broken into separate key prefix ranges, to support parallel processing:

    [db name]_[volume id]
    [db name]_[volume id]_[key prefix]

E.g.
 
	refseq50_1_a
	refseq50_1_b
	refseq50_1_z
	
	refseq50_2_a
	refseq50_2_b
	etc.
