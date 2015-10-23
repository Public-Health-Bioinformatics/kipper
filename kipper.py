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




CODE_VERSION = '1.0.0'
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
		self.output_file = None # By default, printed to stdout
		self.volume_id = None
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

			self.db_scan_action(KEYDB_EXTRACT)
			return

		if options.revert == True: 
			if not (options.version_id or options.dateTime or options.unixTime):
				stop_err('Error: Please supply a version id (-n [number]) or date (-d [date]) to revert to.')

			# Send database back to given revision
			if self.output_file and self.output_file == os.path.dirname(self.db_master_file_path):
				self.output_file = self.get_db_path() 
			self.db_scan_action(KEYDB_REVERT)
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
			old_key = ''
			while db_key_value:

				(created_vid, deleted_vid, db_key, restofline) = db_key_value.split(self.delim, 3)
				version = versions[self.version_dict_lookup(version_ids, long(created_vid), import_modified)]
				version['rows'] +=1
				if old_key != db_key:
					version['keys'] +=1
					old_key = db_key

				version['inserts'] += 1
				if deleted_vid:
					version = versions[self.version_dict_lookup(version_ids, long(deleted_vid), import_modified)]
					version['deletes'] += 1
				
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
			'rows': 0,
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

	def db_scan_action (self, action):
		"""
		#Python 2.6 needs this reopened if it was previously closed.
		#sys.stdout = open("/dev/stdout", "w")
		"""
		dbReader = bigFileReader(self.get_db_path())
		# Setup temp file:
		if self.output_file:
			temp_file = self.get_temp_output_file(action=action)
		
		# Use temporary file so that db_output_file_path switches to new content only when complete
		with (temp_file if self.output_file else sys.stdout) as output:
			db_key_value = dbReader.read()
				
			while db_key_value:
				if action == KEYDB_EXTRACT:
					okLines = self.version_extract(db_key_value)
				
				elif action == KEYDB_REVERT:
					okLines = self.version_revert(db_key_value)

				if okLines:
					output.writelines(okLines)
					 
				db_key_value = dbReader.read()		

		# Issue: metadata lock while quick update with output_file???
		if self.output_file:		
			if action == KEYDB_EXTRACT:
				self.processor.postprocess_file(temp_file.name)

			# Is there a case where we fail to get to this point?
			os.rename(temp_file.name, self.output_file)

			if action == KEYDB_REVERT:
				# When reverting, clear all volumes having versions > self.version_id
				# Takes out volume structure too.
				volumes = self.metadata['volumes']
				for volptr in range(len(volumes)-1, -1, -1):
					volume = volumes[volptr]
					if volume['floor_id'] > self.version_id: #TO REVERT IS TO KILL ALL LATER VOLUMES.
						os.remove(self.get_db_path(volume['id']))	
					versions = volume['versions']
					for verptr in range(len(versions)-1, -1, -1):
						if	versions[verptr]['id'] > self.version_id:
							popped = versions.pop(verptr)
					if len(versions) == 0 and volptr > 0:
						volumes.pop(volptr)
					
			self.write_metadata(self.metadata)


	def db_scan_line(self, db_key_value):
		"""
		FUTURE: transact_code will signal how key/value should be interpreted, to
		allow for differential change storage from previous entries.
		"""
		# (created_vid, deleted_vid, transact_code, restofline) = db_key_value.split(self.delim,3)
		(created_vid, deleted_vid, restofline) = db_key_value.split(self.delim,2)
		if deleted_vid: deleted_vid = long(deleted_vid)
		return (long(created_vid), deleted_vid, restofline)


	def version_extract(self, db_key_value):
		(created_vid, deleted_vid, restofline) = self.db_scan_line(db_key_value)

		if created_vid <= self.version_id and (not deleted_vid or deleted_vid > self.version_id):
			return self.processor.postprocess_line(restofline)

		return False


	def version_revert(self, db_key_value):
		"""
		Reverting database here.
		"""
		(created_vid, deleted_vid, restofline) = self.db_scan_line(db_key_value)

		if created_vid <= self.version_id:
			if (not deleted_vid) or deleted_vid <= self.version_id:
				return [str(created_vid) + self.delim + str(deleted_vid) + self.delim + restofline] 
			else:
				return [str(created_vid) + self.delim + self.delim + restofline] 
		return False
		
		
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
		
		path = os.path.normpath(file)
		# make sure any relative paths are converted to absolute ones
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
			
		@uses self.db_import_file_path string	A file full of one line key[tab]value records.
		@uses self.output_file string	A file to save results in.  If empty, then stdio.
		
		@uses dateTime string		Date time to mark created/deleted records by.
		@puses delim char		Separator between key/value pairs.ake it the function. 
	
		@param file_name name of file being imported.  This is stored in version record so that output file will be the same.
		"""
		delim = self.delim		


		file_size = os.path.getsize(self.db_import_file_path)
		if version_index == None:
			version_index = str(self.get_last_version()+1)

		self.volume_id = self.metadata['volumes'][-1]['id'] #For get_db_path() call below.

		if self.output_file:
			temp_file = self.get_temp_output_file(action=KEYDB_IMPORT, path=self.get_db_path())

			# We want to update database here when output file is db itself.
			if os.path.isdir(self.output_file):  
				self.output_file = self.get_db_path()
	
		version = self.metadata_create_version(import_modified, file_name, file_size, version_index)
		version_id = str(version['id'])
			
		with (temp_file if self.output_file else sys.stdout) as outputFile : 
			dbReader = bigFileReader(self.get_db_path())
			importReader = bigFileReader(self.db_import_file_path)
			old_import_key=''

			while True:
				
				db_key_value = dbReader.turn()
				#if import_key_value
				import_key_value = importReader.turn()
				
				# Skip empty or whitespace lines:
				if import_key_value and len(import_key_value.lstrip()) == 0:
					import_key_value = importReader.read()
					continue
					
				if not db_key_value: # eof
					while import_key_value: # Insert remaining import lines:
						(import_key, import_value) = self.get_key_value(import_key_value)	
						outputFile.write(version_id + delim + delim + import_key + delim + import_value)
						import_key_value = importReader.read() 
						version['inserts'] += 1
						version['rows'] += 1

						if import_key != old_import_key:
							version['keys'] += 1
							old_import_key = import_key

					break # Both inputs are eof, so exit

				elif not import_key_value: # db has key that import file no longer has, so mark each subsequent db line as a delete of the key (if it isn't already)
					while db_key_value:
						(created_vid, deleted_vid, dbKey, dbValue) = db_key_value.split(delim,3)
						version['rows'] += 1

						if deleted_vid:
							outputFile.write(db_key_value)
						else:
							outputFile.write(created_vid + delim + version_id + delim +  dbKey + delim + dbValue)
							version['deletes'] += 1

						db_key_value = dbReader.read()
					break
				
				else:
					(import_key, import_value) = self.get_key_value(import_key_value)						
					(created_vid, deleted_vid, dbKey, dbValue) = db_key_value.split(delim,3)

					if import_key != old_import_key:
						version['keys'] += 1
						old_import_key = import_key
					
					# All cases below lead to writing a row ...
					version['rows'] += 1

					if import_key == dbKey:
						# When the keys match, we have enough information to act on the current db_key_value content; 
						# therefore ensure on next pass that we read it.
						dbReader.step()
						
						if import_value == dbValue:
							outputFile.write(db_key_value)

							# All past items marked with insert will also have a delete.  Step until we find one
							# not marked as a delete... or a new key.
							if deleted_vid: # Good to go in processing next lines in both files.
								pass
							else:
								importReader.step()
								
						else: # Case where value changed - so process all db_key_values until key no longer matches.  

							# Some future pass will cause import line to be written to db 
							# (when key mismatch occurs) as long as we dont advance it (prematurely).							
							if deleted_vid: 
								#preserve deletion record.
								outputFile.write(db_key_value) 
								
							else:
								# Mark record deletion
								outputFile.write(created_vid + delim + version_id + delim + dbKey + delim + dbValue)
								version['deletes'] += 1
								# Then advance since new key/value means new create 

					else:
						# Natural sort doesn't do text sort on numeric parts, ignores capitalization.
						dbKeySort = natural_sort_key(dbKey)
						import_keySort = natural_sort_key(import_key)
						# False if dbKey less; Means db key is no longer in sync db, 
						if cmp(dbKeySort, import_keySort) == -1:
					
							if deleted_vid: #Already marked as a delete
								outputFile.write(db_key_value)
								
							else:	# Write dbKey as a new delete
								outputFile.write(created_vid + delim + version_id + delim + dbKey + delim + dbValue)
								version['deletes'] += 1
							# Advance ... there could be another db_key_value for deletion too.
							dbReader.step() 

						else: #DB key is greater, so insert import_key,import_value in db.
							# Write a create record
							outputFile.write(version_id + delim + delim + import_key + delim + import_value)
							version['inserts'] += 1
							importReader.step() # Now compare next two candidates.

		if self.output_file:
			# Kipper won't write an empty version - since this is usually a mistake.
			# If user has just added new volume though, then slew of inserts will occur
			# even if version is identical to tail end of previous volume version.
			if version['inserts'] > 0 or version['deletes'] > 0:
				#print "Temp file:" + temp_file.name
				os.rename(temp_file.name, self.output_file)
				self.write_metadata(self.metadata)
			else:
				os.remove(temp_file.name)


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
				
		
	# May want to move this to individual data store processor since it can be sensitive to different kinds of whitespace then.
	def get_key_value(self, key_value):	
		# ACCEPTS SPLIT AT ANY WHITESPACE PAST KEY BY DEFAULT
		kvparse = key_value.split(None,1)
		#return (key_value[0:kvptr], key_value[kvptr:].lstrip())
		return (kvparse[0], kvparse[1] if len(kvparse) >1 else '')


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
		sort_a = subprocess.call(['sort','-sfV','-t\t','-k1,1', '-o',temp.name, temp.name])
		return temp #Enables temp file name to be used by caller.
		

	def preprocess_validate_file(self, file_path):
	
		# Do import file preprocessing: 
		# 1) Mechanism to verify if downloaded file is complete - check md5 hash?
		# 4) Could test file.newlines(): returns \r, \n, \r\n if started to read file (1st line).
		# 5) Could auto-uncompress .tar.gz, bz2 etc.
		# Ensures "[key]	[value]" entries are sorted
		# "sort --check ..." returns nothing if sorted, or e.g "sort: sequences_A.fastx.sorted:12: disorder: >114 AJ009959.1 … "

		# if not subprocess.call(['sort','--check','-V',db_import_file_path]): #very fast check
		#	subprocess.call(['sort','-V',db_import_file_path]):
	
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
		
		import stat
		
		# TEST sort failure: set it so temp file is read only.
		#mode = os.stat(temp.name)[stat.ST_MODE]
		#os.chmod(temp.name,mode & ~0222)
		
		# Is this a consideration for natural sort in Python vs bash sort?:
		# *** WARNING *** The locale specified by the environment affects sort order.
		# Set LC_ALL=C to get the traditional sort order that uses native byte values.  
		#-s stable; -f ignore case; V natural sort (versioning) ; -k column, -t tab delimiter
		try:
			subprocess.check_call(['sort', '-sfV', '-t\t', '-k1,1', '-o',temp.name, temp.name])
		except subprocess.CalledProcessError as e:
			stop_err("Error: Sort of import file could not be completed, sort() returned error code " + str(e.returncode) )
		except OSError as e:
			stop_err("Error: Sort of import file could not be completed, sort command or %s file not found?" % temp.name)
			
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
		sequences= self.split_len(line_data[2],80)
		if len(sequences) and sequences[-1].strip() == '':
			sequences[-1] = ''			

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
	than file size improves performance by at least 30% over readline().

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



# Enables use of with ... syntax.  See https://mail.python.org/pipermail/tutor/2009-November/072959.html
class myGzipFile(gzip.GzipFile):
    def __enter__(self):
        if self.fileobj is None:
            raise ValueError("I/O operation on closed GzipFile object")
        return self

    def __exit__(self, *args):
        self.close()


def natural_sort_key(s, _nsre = REGEX_NATURAL_SORT):
	return [int(text) if text.isdigit() else text.lower()
		for text in re.split(_nsre, s)] 


def generic_linux_sort(self):
	import locale
	locale.setlocale(locale.LC_ALL, "C")
	yourList.sort(cmp=locale.strcoll)


def parse_date(adate):
	"""
	Convert human-entered time into linux integer timestamp

	@param adate string Human entered date to parse into linux time

	@return integer Linux time equivalent or 0 if no date supplied
	"""
	adate = adate.strip()
	if adate > '':
	    adateP = parser2.parse(adate, fuzzy=True)
	    #dateP2 = time.mktime(adateP.timetuple())
	    # This handles UTC & daylight savings exactly
	    return calendar.timegm(adateP.timetuple())
	return 0


if __name__ == '__main__':

	kipper = Kipper()
	kipper.__main__()
	
