#!/usr/bin/python
# -*- coding: utf-8 -*-

import subprocess
import datetime
import dateutil.parser as parser2
import calendar
import optparse
import re
import os
import sys
from shutil import copy
import tempfile
import json
import glob
import gzip
#https://code.google.com/p/google-diff-match-patch/wiki/API
import diff_match_patch as dmp_module
import six # A step towards python 3.0 compatibility


CODE_VERSION = '1.1.0'
REGEX_NATURAL_SORT = re.compile('([0-9]+)')
KEYDB_LIST = 1
KEYDB_EXTRACT = 2
KEYDB_REVERT = 3
KEYDB_IMPORT = 4

class MyParser(optparse.OptionParser):
	"""
	Provides a better class for displaying formatted help info.
	From http://stackoverflow.com/questions/1857346/python-optparse-how-to-include-additional-info-in-usage-output.
	"""
	def format_epilog(self, formatter):
		return self.epilog

def stop_err( msg ):
    sys.stderr.write("%s\n" % msg)
    sys.exit(1)

class Kipper(object):

	
	def __init__(self):
		# Provide defaults
		self.db_master_file_name = None
		self.db_master_file_path = None
		self.metadata_file_path = None		
		self.db_import_file_path = None
		self.output = None # Either a file or stdout
		self.output_file = None # File path
		self.volume_id = None
		self.version = None
		self.version_id = None # Note, this is natural #, starts from 1; 
		self.metadata = None
		self.options = None
		self.compression = ''

		_nowabout = datetime.datetime.utcnow() 
		self.dateTime = long(_nowabout.strftime("%s"))

		self.delim = "\t"
		self.nl = "\n"
	

	def __main__(self):
		"""
		Handles all command line options for creating kipper archives, and extracting or reverting to a version.
		""" 
		options, args = self.get_command_line()
		self.options = options

		if options.code_version:
			print CODE_VERSION
			return CODE_VERSION
	
		# *********************** Get Master kipper file ***********************
		if not len(args):
			stop_err('A Kipper database file name needs to be included as first parameter!')
			
		self.db_master_file_name = args[0] #accepts relative path with file name
		
		self.db_master_file_path = self.check_folder(self.db_master_file_name, "Kipper database file")
		# db_master_file_path is used from now on; db_master_file_name is used just for metadata labeling.  
		# Adjust it to remove any relative path component.
		self.db_master_file_name = os.path.basename(self.db_master_file_name)
		
		if os.path.isdir(self.db_master_file_path):
			stop_err('Error: Kipper data file "%s" is actually a folder!' % (self.db_master_file_path) )

		self.metadata_file_path = self.db_master_file_path + '.md'
		
		# Returns path but makes sure its folder is real.  Must come before get_metadata()
		self.output_file = self.check_folder(options.db_output_file_path)

		
		# ************************* Get Metadata ******************************
		if options.initialize: 
			if options.compression:
				self.compression = options.compression
				
			self.set_metadata(type=options.initialize, compression=self.compression)
			
		self.get_metadata(options);

		self.check_date_input(options)

		if options.version_id or (options.extract and options.version_index):
			if options.version_index:
				vol_ver = self.version_lookup(options.version_index)
				
			else:
				# Note version_id info overrides any date input above.
				vol_ver = self.get_version(options.version_id)
			
			if not vol_ver:
				stop_err("Error: Given version number or name does not exist in this database")
				
			(volume, version) = vol_ver
			self.volume_id = volume['id']
			self.version_id = version['id']
			self.dateTime = float(version['created'])
		else:
			# Use latest version by default
			if not self.version_id and len(self.metadata['volumes'][-1]['versions']) > 0:
				self.volume_id = self.metadata['volumes'][-1]['id']
				self.version_id = self.metadata['volumes'][-1]['versions'][-1]['id']
			
		# ************************** Action triggers **************************
		
		if options.volume == True: 
			# Add a new volume to the metadata
			self.metadata_create_volume()
			self.write_metadata(self.metadata)
			
		if options.db_import_file_path != None:
			# Any time an import file is specified, this is the only action:
			self.try_import_file(options)
			return
		
		if options.metadata == True: 
			# Writes metadata to disk or stdout
			self.write_metadata2(self.metadata)
			return
		
		if options.extract == True:
			# Defaults to pulling latest version
			if not (self.version_id):
				stop_err('Error: Please supply a version id (-n [number]) or date (-d [date]) to extract.')

			if self.output_file and os.path.isdir(self.output_file):
				# A general output file name for the data store as a whole
				output_name = self.metadata['file_name'] 
				if output_name == '':
					# Get output file name from version's original import file_name
					output_name = self.metadata['volumes'][self.volume_id-1]['versions'][self.version_id-1]['file_name']
					# But remove the .gz suffix if it is there (refactor later).
					if output_name[-3:] == '.gz':
						output_name = output_name[0:-3]
				self.output_file = os.path.join(self.output_file, output_name)

			self.db_action_extract()
			return

		if options.revert == True: 
			if not (options.version_id or options.dateTime or options.unixTime):
				stop_err('Error: Please supply a version id (-n [number]) or date (-d [date]) to revert to.')

			# Send database back to given revision
			if self.output_file and self.output_file == os.path.dirname(self.db_master_file_path):
				self.output_file = self.get_db_path() 
			self.db_action_revert()
			return
	
		# Default to list datastore versions
		self.get_list()
		

	def get_db_path(self, volume_id = None):
		#Note: metadata must be established before this method is called.
		if volume_id is None: volume_id = self.volume_id
		return self.db_master_file_path + '_' + str(volume_id) + self.metadata['compression']


	def get_temp_output_file(self, action = None, path=None):
		# Returns write handle (+name) of temp file.  Returns gzip interface if compression is on.
		if path == None:
			path = self.output_file

		temp = tempfile.NamedTemporaryFile(mode='w+t',delete=False, dir=os.path.dirname(path) )

		# If compression is called for, then we have to switch to gzip handler on the temp name:
		if action in [KEYDB_REVERT, KEYDB_IMPORT] and self.metadata['compression'] == '.gz':
			temp.close()
			temp = myGzipFile(temp.name, 'wb')

		return temp

	 
	def get_list(self):	
		"""
		Default listing of volumes and versions
		"""
		volumes = self.metadata['volumes']
		for ptr in range(0, len(volumes)):
			volume = volumes[ptr]
			if ptr < len(volumes)-1:
				ceiling = str(volumes[ptr+1]['floor_id'] - 1)
			else:
				ceiling = ''
			print "Volume " + str(ptr+1) + ", Versions " + str(volume['floor_id']) + "-" + ceiling

			for version in volume['versions']:
				print str(version['id']) + ": " + self.dateISOFormat(float(version['created'])) + '_v' + version['name']


	def set_metadata(self, type='text', compression=''):
		"""
		Request to initialize metadata file
		Output metadata to stdio or to -o output file by way of temp file.
		If one doesn't include -o, then output goes to stdio; 
		If one includes only -o, then output overwrites .md file.
		If one includes -o [filename] output overwrites [filename]
		
		Algorithm processes each line as it comes in database.  This means there
		is no significance to the version_ids ordering; earlier items in list can
		in fact be later versions of db.  So must resort and re-assign ids in end.
		@param type string text or fasta etc.
		"""	
		if os.path.isfile(self.metadata_file_path):
			stop_err('Error: Metadata file "%s" exists.  You must remove it before generating a new one.' % (self.metadata_file_path) )
			
		self.metadata_create(type, compression)
							
		volumes = glob.glob(self.db_master_file_path + '_[0-9]*')

		volumes.sort(key=lambda x: natural_sort_key(x))
		for volume in volumes:
			# Note: scanned volumes must be consecutive from 1.  No error detection yet.
			self.metadata_create_volume(False)
			versions = self.metadata['volumes'][-1]['versions']
			import_modified = os.path.getmtime(volume)
			dbReader = bigFileReader(volume)
			version_ids = []
			db_key_value = dbReader.read()				
			while db_key_value:

				(db_key, created_vid, restofline) = self.db_scan_line(db_key_value)

				transactions = json.loads(restofline)
				for (ptr, transaction) in enumerate(transactions):

					version = versions[self.version_dict_lookup(version_ids, transaction[0], import_modified)]
					if len(transaction) == 1: 
						version['deletes'] += 1
					else: 
						version['keys'] +=1
						if ptr == 0:
							version['inserts'] += 1
						else:
							version['updates'] += 1

				db_key_value = dbReader.read()

			# Reorder, and reassign numeric version ids:
			versions.sort(key=lambda x: x['id'])
			for ptr, version in enumerate(versions):
				version['id'] = ptr+1

		# If first master db volume doesn't exist, then this is an initialization situation
		if len(volumes) == 0:
			self.metadata_create_volume()
			self.create_volume_file()
	
		with open(self.metadata_file_path,'w') as metadata_handle:
			metadata_handle.write(json.dumps(self.metadata, sort_keys=True, indent=4, separators=(',', ': ')))
		
		return True

	
	def get_metadata(self, options):
		"""
		Read in json metadata from file, and set file processor [fasta|text] engine accordingly.
		"""

		if not os.path.isfile(self.metadata_file_path):
			#stop_err('Error: Metadata file "%s" does not exist.  You must regenerate it with the -m option before performing other actions.' % (self.metadata_file_path) )
			stop_err('Error: Unable to locate the "%s" metadata file.  It should accompany the "%s" file.  Use the -M parameter to initialize or regenerate the basic file.' % (self.metadata_file_path, self.db_master_file_name) )

		with open(self.metadata_file_path,'r') as metadata_handle:
			self.metadata = json.load(metadata_handle)
			
		# ******************* Select Kipper Pre/Post Processor **********************
		# FUTURE: More processor options here - including custom ones referenced in metadata
		if self.metadata['type'] == 'fasta':
			self.processor = VDBFastaProcessor() # for fasta sequence databases
		else:
			self.processor = VDBProcessor() # default text
			
		# Handle any JSON metadata defaults here for items that aren't present in previous databases.
		if not 'compression' in self.metadata:
			self.metadata['compression'] = ''
			
		
	def write_metadata(self, content):
		"""
		Called when data store changes occur (revert and import). 
		If they are going to stdout then don't stream metadata there too.
		""" 
		if self.output_file: self.write_metadata2(content)


	def write_metadata2(self,content):
	
		with (open(self.metadata_file_path,'w') if self.output_file else sys.stdout) as metadata_handle:
			metadata_handle.write(json.dumps(content, sort_keys=True, indent=4, separators=(',', ': ')))


	def metadata_create(self, type, compression, floor_id=1):
		""" 
		Initial metadata structure
		"""
		file_name = self.db_master_file_name.rsplit('.',1)
		self.metadata = {
			'version': CODE_VERSION,
			'name': self.db_master_file_name, 
			'db_file_name': self.db_master_file_name,
			# A guess about what best base file name would be to write versions out as
			'file_name': file_name[0] + '.' + type, 
			'type': type,
			'description': '',
			'processor': '', # Processing that overrides type-matched processor.
			'compression': self.compression,
			'volumes': []
		}
		

	def metadata_create_volume(self, file_create = True):
		# Only add a volume if previous volume has at least 1 version in it.
		if len(self.metadata['volumes']) == 0 or len(self.metadata['volumes'][-1]['versions']) > 0:
			id = len(self.metadata['volumes']) + 1
			volume = {
				'floor_id': self.get_last_version()+1,
				'id': id,
				'versions': []
			}
			self.metadata['volumes'].append(volume)
			self.volume_id = id
			if file_create:
				self.create_volume_file()
				
			
			return id
			
		else:
			stop_err("Error: Didn't create a new volume because last one is empty already.")


	def create_volume_file(self):

		if self.metadata['compression'] == '.gz':
			gzip.open(self.get_db_path(), 'wb').close()
		else:
			open(self.get_db_path(),'w').close()			


	def metadata_create_version(self, mydate, file_name = '', file_size = 0, version_name = None):
		id = self.get_last_version()+1
		if version_name == None:
			version_name = str(id)

		version = {
			'id': id,
			'created': mydate,
			'name': version_name,
			'file_name': file_name,
			'file_size': file_size,
			'inserts': 0,
			'deletes': 0,
			'updates': 0,
			# 'rows': 0,
			'keys': 0
		}
		self.metadata['volumes'][-1]['versions'].append(version)
		
		return version


	def get_version(self, version_id = None):
		if version_id is None: 
			version_id = self.version_id
		
		for volume in self.metadata['volumes']:
			for version in volume['versions']:
				if version_id == version['id']:
					return (volume, version)
		
		return False


	def version_lookup(self, version_name):
		for volume in self.metadata['volumes']:
			for version in volume['versions']:
				if version_name == version['name']:
					return (volume, version)
		
		return False
		
		
	def version_dict_lookup(self, version_ids, id, timestamp = None):
		if id not in version_ids: 
			version_ids.append(id)
			version = self.metadata_create_version(timestamp)

		return version_ids.index(id)
	

	#****************** Methods Involving Scan of Master Kipper file **********************

	def db_action_extract (self):
		"""
		#STDOUT Issue: Python 2.6 needs this reopened if it was previously closed.
		#sys.stdout = open("/dev/stdout", "w")
		"""
		dbReader = bigFileReader(self.get_db_path())
		# Setup temp file:
		if self.output_file: temp_file = self.get_temp_output_file(action=KEYDB_EXTRACT)
		
		# Use temporary file so that db_output_file_path switches to new content only when complete
		with (temp_file if self.output_file else sys.stdout) as self.output:
			db_key_value = dbReader.read()
			
			while db_key_value:
				# Old version: only one of the lines would match a particular version id.
				# New version: process each line until past self.version_id

				(dbKey, created_vid, restofline) = self.db_scan_line(db_key_value)

				#If we have an item that has creation <= retrieval version,
				if created_vid <= self.version_id:
					transactions = json.loads(restofline)
					dbValue = '' # Begin building value
					delete = False
					for (transaction) in transactions:
						if transaction[0] <= self.version_id: 
							if len(transaction) == 1: 
								delete = True
								dbValue = '' #Start from beginning
							else: 
								delete = False
								dbValue = self.diff_apply_patch(dbValue, transaction[1])
						else:
							break


					if not delete: # If this isn't a fresh delete, write it
						self.output.writelines(self.processor.postprocess_line(dbKey + self.delim + dbValue))

				db_key_value = dbReader.read()	

		# Postprocess and swap temp file back into named output file
		if self.output_file:		
			self.processor.postprocess_file(temp_file.name)
			os.rename(temp_file.name, self.output_file)					



	def db_action_revert (self):
		"""
		Revert volumes and metadata back to a particular version (self.version_id)
		"""
		dbReader = bigFileReader(self.get_db_path())

		if self.output_file: temp_file = self.get_temp_output_file(action=KEYDB_REVERT)
		
		with (temp_file if self.output_file else sys.stdout) as self.output:
			db_key_value = dbReader.read()

			while db_key_value:

				(dbKey, created_vid, restofline) = self.db_scan_line(db_key_value)

				#If we have an item that has creation <= revert version,
				if created_vid <= self.version_id:
					transactions = json.loads(restofline)

					for (ptr, transaction) in enumerate(transactions):
						# As soon as we encounter our first transaction happened after
						# revert version, chop transactions back to that point.
						if (transaction[0] > self.version_id): 
							transactions = transactions[0:ptr]
							break

					dbValue = json.dumps(transactions, separators=(',',':'))
					self.db_output_write(dbKey, str(created_vid), dbValue)

				db_key_value = dbReader.read()


		# Issue: metadata lock while quick update with output_file???
		if self.output_file:		

			self.volume_revert() # Side effect required: revert triggers change in metadata
			os.rename(temp_file.name, self.output_file)					


	def db_output_write(self, dbKey, created_vid, dbValue):

		self.output.write(dbKey + self.delim + str(created_vid) + self.delim + dbValue + self.nl)


	def db_scan_line(self, db_key_value):
		"""
		"""
		(key, created_vid, restofline) = db_key_value.split(self.delim,2)
		return (key, long(created_vid), restofline)



	def volume_revert(self):
		'''
		Revise metadata to only include volumes/versions up to given version_id
		'''
		# Clear all volumes having versions > self.version_id
		volumes = self.metadata['volumes']
		for volptr in range(len(volumes)-1, -1, -1):
			volume = volumes[volptr]
			if volume['floor_id'] > self.version_id: 
				# Delete all later volume files.
				os.remove(self.get_db_path(volume['id']))	
			versions = volume['versions']
			for verptr in range(len(versions)-1, -1, -1):
				if	versions[verptr]['id'] > self.version_id:
					popped = versions.pop(verptr)
			if len(versions) == 0 and volptr > 0:
				volumes.pop(volptr)
		self.write_metadata(self.metadata)


	def check_date_input(self, options):
		"""
		"""
		if options.unixTime != None:
			try: 
				_userTime = float(options.unixTime) 
				# if it is not a float, triggers exception
			except ValueError:	
				stop_err("Given Unix time could not be parsed [" + options.unixTime + "].  Format should be [integer]")

		elif options.dateTime != None:
		
			try: 
				_userTime = parse_date(options.dateTime)
				
			except ValueError:
				stop_err("Given date could not be parsed [" + options.dateTime + "].  Format should include at least the year, and any of the other more granular parts, in order: YYYY/MM/DD [H:M:S AM/PM]")	

		else:
			return False
			
		_dtobject = datetime.datetime.fromtimestamp(float(_userTime)) #
		self.dateTime = long(_dtobject.strftime("%s"))


		# Now see if we can set version_id by it.  We look for version_id that has created <= self.dateTime 
		for volume in self.metadata['volumes']:
			for version in volume['versions']:
				if version['created'] <= self.dateTime:
					self.version_id = version['id']
					self.volume_id = volume['id']
				else:
					break
					
		return True	
	

	def check_folder(self, file_path, message = "Output directory for "):
		"""
		Ensures file folder path for output file exists.
		We don't want to create output in a mistaken location.
		"""
		if file_path != None:

			path = os.path.normpath(file_path)
			if not os.path.isdir(os.path.dirname(path)): 
				# Not an absolute path, so try default folder where script launched from:
				path = os.path.normpath(os.path.join(os.getcwd(), path) )
				if not os.path.isdir(os.path.dirname(path)):
					stop_err(message + "[" + path + "] does not exist!")			
					
			return path
		return None


	def check_file_path(self, file, message = "File "):
		""" 
			Converts path if it is relative, to an absolute one.
		"""
		path = os.path.normpath(file)

		if not os.path.isdir(os.path.dirname(path)) or not os.path.isfile(path): 
			# Not an absolute path, so try default folder where script was called:
			path = os.path.normpath(os.path.join(os.getcwd(),path) )
			if not os.path.isfile(path):
				stop_err(message + "[" + path + "] doesn't exist!")
		return path


	def try_import_file(self, options):
		"""
		Create new version from comparison of import data file against Kipper
		Note "-o ." parameter enables writing back to master database.
		"""
		self.db_import_file_path = self.check_file_path(options.db_import_file_path, "Import data file ")
		
		check_file = self.processor.preprocess_validate_file(self.db_import_file_path)
		if not check_file:
			stop_err("Import data file isn't sorted or composed correctly!")
		
		# SET version date to creation date of import file.
		import_modified = os.path.getmtime(self.db_import_file_path)

		original_name = os.path.basename(self.db_import_file_path)
		# creates a temporary file, which has conversion into 1 line key-value records
		temp = self.processor.preprocess_file(self.db_import_file_path)
		if (temp):

			self.db_import_file_path = temp.name
		
			self.import_file(original_name, import_modified, options.version_index)
			
			os.remove(temp.name)


	def import_file(self, file_name, import_modified, version_index = None):
		"""
		Imports from an import file (or temp file if transformation done above) to
		temp Kipper version which is copied over to main database on completion.
		
		Import algorithm only works if the import file is already sorted in the same way as the Kipper database file
		DATABASE KEY entry has value which encodes differential changes for all versions. 
		It also includes a "x:1" delete flag to indicate if a particular version no longer has 
		key

		@uses self.db_import_file_path string	A file full of one line key[tab]value records.
		@uses self.output_file string	A file to save results in.  If empty, then stdio.
		
		@uses dateTime string		Date time to mark created/deleted records by.
		@puses delim char		Separator between key/value pairs.ake it the function. 
	
		@param file_name name of file being imported.  This is stored in version record so that output file will be the same.
		"""

		file_size = os.path.getsize(self.db_import_file_path)
		if version_index == None:
			version_index = str(self.get_last_version()+1)

		self.volume_id = self.metadata['volumes'][-1]['id'] #For get_db_path() call below.

		if self.output_file:
			temp_file = self.get_temp_output_file(action=KEYDB_IMPORT, path=self.get_db_path())

			# We want to update database here when output file is db itself.
			if os.path.isdir(self.output_file):  
				self.output_file = self.get_db_path()
	
		# Add new version identifier to metadata
		self.version = self.metadata_create_version(import_modified, file_name, file_size, version_index)

		# VERSION KEYS COUNT COULD BE INITIALIZED FROM PREVIOUS VERSION TO SUPPORT DIFF IMPORT.
		# version['keys'] = ...

		with (temp_file if self.output_file else sys.stdout) as self.output : 
			dbReader = bigFileReader(self.get_db_path())
			importReader = bigFileReader(self.db_import_file_path)
			old_import_key=''

			while True:
				
				import_key_value = importReader.turn()
				
				# Skip empty or whitespace lines:
				if import_key_value and len(import_key_value.lstrip()) == 0:
					import_key_value = importReader.read()
					continue	


				# If no dbReader.step(), then db_key_value is same as old, so skip reparsing.
				if dbReader.take_step:
					db_key_value = dbReader.turn()
					if db_key_value:
						(dbKey, created_vid, dbTransactionStr) = self.db_scan_line(db_key_value)


				if not db_key_value: # eof
					self.import_file_remaining(importReader, import_key_value) 							
					break # Both files now processed

				elif not import_key_value: 
					self.import_db_remaining(dbReader, db_key_value)
					break
				
				(import_key, import_value) = self.get_key_value(import_key_value)

				# Subsequent instances of any duplicated key are ignored:
				if import_key == old_import_key:
					old_import_key = import_key
					importReader.step()
					continue
				

				if import_key == dbKey:
					
					# Calculate current value 
					(dbValue, transactions) = self.diff_apply_transactions(dbTransactionStr)

					# Now we have latest db Value to compare input with
					if import_value == dbValue: 
						# No change in key value.  SHORTCUT write.
						self.output.write(db_key_value)
						self.version['keys'] += 1
					
					# Case where value changed: add update transaction
					else: 
						self.import_write_update(dbKey, dbValue, import_value, transactions)

					dbReader.step()
					importReader.step()

				else:
					# Find out whether db key preceeds import key (if so its a delete)
					# Natural sort doesn't do text sort on numeric parts, ignores capitalization.
					# dbKeySort = natural_sort_key(dbKey)
					# import_keySort = natural_sort_key(import_key)
					# False if dbKey less; Means dbKey is no longer in import file, so delete 
					if dbKey < import_key:

						self.import_write_delete(db_key_value)
						dbReader.step() # Check if next dbKey matches import_key

					else: # DB key is greater, so we haven't seen this import_key before.
						
						self.import_write_create(import_key, import_value)
						importReader.step() # Now compare next two candidates.

		if self.output_file:
			# Kipper won't write an empty version - since this is usually a mistake.
			# If user has just added new volume though, then slew of inserts will occur
			# even if version is identical to tail end of previous volume version.
			# I.e. Kipper only writes new version if at least one insert or delete occured.
			if self.version['inserts'] > 0 or self.version['deletes'] > 0 or self.version['updates'] > 0:
				os.rename(temp_file.name, self.output_file)
				self.write_metadata(self.metadata)
			else:
				os.remove(temp_file.name)


	def import_file_remaining(self, importReader, import_key_value):
		'''
		 Insert remaining import file lines
		'''
		old_import_key = ''
		while import_key_value: 
			(import_key, import_value) = self.get_key_value(import_key_value)	
			
			if import_key != old_import_key:
				self.import_write_create(import_key, import_value)
				old_import_key = import_key

			import_key_value = importReader.read() 							


	def import_db_remaining(self, dbReader, db_key_value):
		'''
		Delete remaining db key values (if not already deleted) since import file ended
		''' 
		while db_key_value:

			self.import_write_delete(db_key_value)
			db_key_value = dbReader.read()


	def import_write_delete(self, db_key_value):

			(dbKey, created_vid, dbValue) = self.db_scan_line(db_key_value)
			transactions = json.loads(dbValue)

			# If last transaction for this item has no delta, then it's already a delete
			if len(transactions[-1]) == 1:

				self.output.write(db_key_value)

			else:

				transactions.append([self.version['id']])
				dbValue = json.dumps(transactions, separators=(',',':')) 
				self.db_output_write(dbKey, created_vid, dbValue)

				self.version['deletes'] += 1
				self.version['keys'] -= 1


	def import_write_create(self, import_key, import_value):
		# Create a new import_key/value record in db.
		transactions = [[self.version['id'], self.diff_make_patch('',import_value) ]]
		dbValue = json.dumps(transactions, separators=(',',':')) 
		self.db_output_write(import_key, self.version['id'], dbValue)

		self.version['inserts'] += 1
		self.version['keys'] += 1


	def import_write_update(self, dbKey, dbValue, import_value, transactions):

		transactions.append([self.version['id'], self.diff_make_patch(dbValue, import_value)])
		dbValue = json.dumps(transactions, separators=(',',':')) 
		self.db_output_write(dbKey, transactions[0][0], dbValue)

		self.version['updates'] += 1


	def get_last_version(self):
		"""
		Returns first Volume version counting from most recent.
		Catch is that some volume might be empty, so have to go to previous one
		"""
		for ptr in range(len(self.metadata['volumes'])-1, -1, -1):
			versions = self.metadata['volumes'][ptr]['versions']
			if len(versions) > 0:
				return versions[-1]['id']
				
		return 0	


	def get_key_value(self, key_value):	
		'''
		ACCEPTS SPLIT AT ANY WHITESPACE PAST KEY BY DEFAULT
		May want to move this to individual data store processor since it can be sensitive to different kinds of whitespace then.
		'''
		kvparse = key_value.split(None,1)
		return (kvparse[0], kvparse[1] if len(kvparse) >1 else '')


	def diff_make_patch (self, stringOld, stringNew):
		"""
			Compare old and new strings, formulate differential description of the text deleted, added, or replaced
		"""
		matcher = dmp_module.diff_match_patch()
		diff = matcher.diff_main(stringOld, stringNew)
		matcher.diff_cleanupEfficiency(diff)

		# Convert diff array into form that is set up just to operate on previous string version.
		patch = []
		for (act, value) in diff:
			if act == 1: patch.append(value) # Inserted string
			elif act == 0: patch.append(len(value)) # Unchanged
			else: patch.append(-len(value)) # Delete

		return patch # json.dumps(patch, separators=(',',':'))    


	def diff_apply_patch (self, oldstr, patch):
		'''
		Patch is an array of commands:
		 - a string to insert
		 - a positive # to copy characters from oldstr through
		 - a negative # to skip characters from oldstr
		'''
		newstr = ""
		oldPtr = 0
		for item in patch:
			if isinstance( item, six.string_types ):
				newstr += item
			elif item >= 0:
				newstr += str(oldstr[oldPtr:oldPtr+item])
				oldPtr += item
			else:
				oldPtr += -item # OldPtr is negative, so skip positive # chars.

		return newstr


	def diff_apply_transactions(self, dbValue):

		value = '' # Begin building value.  Shortcut on this test?
		transactions = json.loads(dbValue)
		for (transaction) in transactions:
			if len(transaction) == 1: 
				value = '' #Start from beginning
			else: 
				value = self.diff_apply_patch(value, transaction[1])

		return (value, transactions)


	def dateISOFormat(self, atimestamp):
		return datetime.datetime.isoformat(datetime.datetime.fromtimestamp(atimestamp))


	def get_command_line(self):
		"""
		*************************** Parse Command Line *****************************
		
		"""
		parser = MyParser(
			description = 'Maintains versions of a file-based database with comparison to full-copy import file updates.',
			usage = 'kipper.py [kipper database file] [options]*',
			epilog="""
			
	All outputs go to stdout and affect no change in Kipper database unless the '-o' parameter is supplied.  (The one exception to this is when the -M regenerate metadata command is provided, as described below.)  Thus by default one sees what would happen if an action were taken, but must take an additional step to affect the data.
	
	'-o .' is a special request that leads to:
	  * an update of the Kipper database for --import or --revert actions
	  * an update of the .md file for -M --rebuild action 
   
	As well, when -o parameter is a path, and not a specific filename, then kipper.py looks up what the appropriate output file name is according to the metadata file.
	
	USAGE
	
	Initialize metadata file and Kipper file.
		kipper.py [database file] -M --rebuild [type of database:text|fasta]

	View metadata (json) file.
		kipper.py [database file] -m --metadata
		
	Import key/value inserts/deletes based on import file. (Current date used).
		kipper.py [database file] -i --import [import file]
		e.g.
		kipper.py cpn60 -i sequences.fasta             # outputs new master database to stdout; doesn't rewrite it.
		kipper.py cpn60 -i sequences.fasta -o .        # rewrites cpn60 with new version added.
		
	Extract a version of the file based on given date/time
		kipper.py [database file] -e --extract -d datetime -o [output file]

	Extract a version of the file based on given version Id
		kipper.py [database file] -e --extract -n [version id] -o [output file]

	List versions of dbFile key/value pairs (by date/time)
		kipper.py [database file]
		kipper.py [database file] -l --list

	Have database revert to previous version.  Drops future records, unmarks corresponding deletes.
		kipper.py [database file] -r --revert -d datetime -o [output file]

	Return version of this code:	
		kipper.py -v --version 		
			""")
		
		# Data/Metadata changing actions
		parser.add_option('-M', '--rebuild', type='choice', dest='initialize', choices=['text','fasta'],
			help='(Re)generate metadata file [name of db].md .  Provide the type of db [text|fasta| etc.].')

		parser.add_option('-i', '--import', type='string', dest='db_import_file_path', 
			help='Import key/value inserts/deletes based on delta comparison with import file')
	
		parser.add_option('-e', '--extract', dest='extract', default=False, action='store_true', 
			help='Extract a version of the file based on given date/time')
		
		parser.add_option('-r', '--revert', dest='revert', default=False, action='store_true', 
			help='Have database revert to previous version (-d date/time required).  Drops future records, unmarks corresponding deletes.')

		parser.add_option('-V', '--volume', dest='volume', default=False, action='store_true', 
			help='Add a new volume to the metadata.  New imports will be added here.')
			
		# Passive actions
		parser.add_option('-m', '--metadata', dest='metadata', default=False, action='store_true',
			help='View metadata file [name of db].md')

		parser.add_option('-l', '--list', dest='list', default=False, action='store_true', 
			help='List versions of dbFile key/value pairs (by date/time)')
			
		parser.add_option('-c', '--compression', dest='compression', type='choice', choices=['.gz'], 
			help='Enable compression of database.  options:[.gz]')

		# Used "v" for standard code version identifier.
		parser.add_option('-v', '--version', dest='code_version', default=False, action='store_true', 
			help='Return version of kipper.py code.')

		parser.add_option('-o', '--output', type='string', dest='db_output_file_path',  
			help='Output to this file.  Default is to stdio')

		parser.add_option('-I', '--index', type='string', dest='version_index', 
			help='Provide title (index) e.g. "1.4" of version being imported/extracted.')

		parser.add_option('-d', '--date', type='string', dest='dateTime', 
			help='Provide date/time for sync, extract or revert operations.  Defaults to now.')
		parser.add_option('-u', '--unixTime', type='int', dest='unixTime', 
			help='Provide Unix time (integer) for sync, extract or revert operations.')
		parser.add_option('-n', '--number', type='int', dest='version_id',  
			help='Provide a version id to extract or revert to.')

		return parser.parse_args()


class VDBProcessor(object):
	
	delim = '\t'
	nl = '\n'
	
	#def preprocess_line(self, line):
	#	return [line]
	
	def preprocess_file(self, file_path):
		temp = tempfile.NamedTemporaryFile(mode='w+t',delete=False, dir=os.path.dirname(file_path) )
		copy (file_path, temp.name)
		temp.close()
		env = os.environ.copy()
		env['LC_ALL'] = 'C'
		sort_a = subprocess.call(['sort','-s','-t\t','-k1,1', '-o',temp.name, temp.name], env=env)
		return temp #Enables temp file name to be used by caller.
		

	def preprocess_validate_file(self, file_path):
	
		# Do import file preprocessing: 
		# 1) Mechanism to verify if downloaded file is complete - check md5 hash?
		# 4) Could test file.newlines(): returns \r, \n, \r\n if started to read file (1st line).
		# 5) Could auto-uncompress .tar.gz, bz2 etc.
		# Ensures "[key]	[value]" entries are sorted
		# "sort --check ..." returns nothing if sorted, or e.g "sort: sequences_A.fastx.sorted:12: disorder: >114 AJ009959.1 … "

		# if not subprocess.call(['sort','--check','-sfV',db_import_file_path]): #very fast check
		#	subprocess.call(['sort','-sfV',db_import_file_path]):
	
		return True
		
	def postprocess_line(self, line):
		#Lines are placed in array so that one can map to many in output file
		return [line]

	def postprocess_file(self, file_path):
		return False
		
	def sort(self, a, b):
		pass
		

class VDBFastaProcessor(VDBProcessor):
	
	
	def preprocess_file(self, file_path):
		"""
		Converts input fasta data into one line tab-delimited record format, then sorts.
		"""
		temp = tempfile.NamedTemporaryFile(mode='w+t',delete=False, dir=os.path.dirname(file_path) )
		fileReader = bigFileReader(file_path)
		line = fileReader.read()
		old_line = ''
		while line:
			line = line.strip()
			if len(line) > 0: 

				if line[0] == '>':
					if len(old_line):
						temp.write(old_line + self.nl)
					lineparse = line.split(None,1)
					key = lineparse[0].strip()
					if len(lineparse) > 1:
						description = lineparse[1].strip().replace(self.delim, ' ')
					else:
						description = ''
					old_line = key[1:] + self.delim + description + self.delim
					
				else:
					old_line = old_line + line

			line = fileReader.read()

		if len(old_line)>0:
			temp.write(old_line+self.nl)
			
		temp.close()
		
		# Is this a consideration for natural sort in Python vs bash sort?:
		# *** WARNING *** The locale specified by the environment affects sort order.
		# Set LC_ALL=C to get the traditional sort order that uses native byte values.  
		#-s stable; -f ignore case; V natural sort (versioning) ; -k column, -t tab delimiter
		env = os.environ.copy()
		env['LC_ALL'] = 'C'
		sort_a = subprocess.call(['sort', '-s', '-t\t', '-k1,1', '-o',temp.name, temp.name], env=env)

		return temp #Enables temp file name to be used by caller.
		
		
	def postprocess_line(self, line):
		"""
		Transform Kipper fasta 1 line format key/value back into output file line(s) - an array

		@param line string containing [accession id][TAB][description][TAB][fasta sequence]
		@return string containing lines each ending with newline, except end.
		"""
		line_data =	line.split('\t',2)
		# Set up ">[accession id] [description]\n" :
		fasta_header = '>' + ' '.join(line_data[0:2]) + '\n'
		# Put fasta sequences back into multi-line; note trailing item has newline.
		if len(line_data) > 1:
			sequences= self.split_len(line_data[2],80)
			if len(sequences) and sequences[-1].strip() == '':
				sequences[-1] = ''
		else:
			sequences = []

		return fasta_header + '\n'.join(sequences)


	def split_len(self, seq, length):
		return [seq[i:i+length] for i in range(0, len(seq), length)]


class bigFileReader(object):
	"""
	This provides some advantage over reading line by line, and as well has a system
	for skipping/not advancing reads - it has a memory via "take_step" about whether
	it should advance or not - this is used when the master database and the import 
	database are feeding lines into a new database.
	 
	Interestingly, using readlines() with byte hint parameter less 
	than file size seems to improve performance by at least 30% over readline().

	FUTURE: Adjust buffer lines dynamically based on file size/lines ratio?
	"""

	def __init__(self, filename):
		self.lines = []
		# This simply allows any .gz repository to be opened
		# It isn't connected to the Kipper metadata['compression'] feature.
		if filename[-3:] == '.gz':
			self.file = gzip.open(filename,'rb')
		else:
			self.file = open(filename, 'rb', 1)

		self.line = False
		self.take_step = True
		self.buffer_size=1000 # Number of lines to read into buffer.


	def turn(self):
		"""
		When accessing bigFileReader via turn mechanism, we get current line if no step;
		otherwise with step we read new line. 
		"""
		if self.take_step == True:
			self.take_step = False
			return self.read()
		return self.line


	def read(self):
		if len(self.lines) == 0: 
			self.lines = self.file.readlines(self.buffer_size)
		if len(self.lines) > 0:
			self.line = self.lines.pop(0) 
			#if len(self.lines) == 0:
			#	self.lines = self.file.readlines(self.buffer_size)
			#make sure each line doesn't include carriage return
			return self.line
			
		return False 


	def readlines(self):
		"""
		Small efficiency: 
		A test on self.lines after readLines() call can control loop.
		Bulk write of remaining buffer; ensures lines array isn't copied 
		but is preserved when self.lines is removed
		"""
		self.line = False
		if len(self.lines) == 0:
			self.lines = self.file.readlines(self.buffer_size)
		if len(self.lines) > 0:
			shallowCopy = self.lines[:]
			self.lines = self.file.readlines(self.buffer_size)
			return shallowCopy 
		return False


	def step(self):
		self.take_step = True



class myGzipFile(gzip.GzipFile):
	"""
	# Enables use of "with [expression]:" syntax.  
	See https://mail.python.org/pipermail/tutor/2009-November/072959.html
	"""
	def __enter__(self):
		if self.fileobj is None:
			raise ValueError("I/O operation on closed GzipFile object")
		return self

	def __exit__(self, *args):
		self.close()


def natural_sort_key(s, _nsre = REGEX_NATURAL_SORT):
	return [int(text) if text.isdigit() else text.lower()
		for text in re.split(_nsre, s)] 


def generic_linux_sort(self, aList):
	import locale
	locale.setlocale(locale.LC_ALL, "C")
	aList.sort(cmp=locale.strcoll)


def parse_date(adate):
	"""
	Convert human-entered time into linux integer timestamp
	This handles UTC & daylight savings exactly

	@param adate string Human entered date to parse into linux time
	@return integer Linux time equivalent or 0 if no date supplied
	"""
	adate = adate.strip()
	if adate == '':return 0

	adateP = parser2.parse(adate, fuzzy=True)
	return calendar.timegm(adateP.timetuple())
	

if __name__ == '__main__':

	kipper = Kipper()
	kipper.__main__()
	
