#!/usr/bin/env python

# Matthieu Brucher
# Last Change : 2008-11-19 19:05
# Revised Damion Dooley 2015-04-19 to provide absolute memory consumption, tabular datafile only

import subprocess
import threading
import datetime
import re
import csv

names = [("pid", int),
         ("comm", str),
         ("state", str),
         ("ppid", int),
         ("pgrp", int),
         ("session", int),
         ("tty_nr", int),
         ("tpgid", int),
         ("flags", int),
         ("minflt", int),
         ("cminflt", int),
         ("majflt", int),
         ("cmajflt", int),
         ("utime", int),
         ("stime", int),
         ("cutime", int),
         ("cstime", int),
         ("priority", int),
         ("nice", int),
         ("0", int),
         ("itrealvalue", int),
         ("starttime", int),
         ("vsize", int),
         ("rss", int),
         ("rlim", int),
         ("startcode", int),
         ("endcode", int),
         ("startstack", int),
         ("kstkesp", int),
         ("kstkeip", int),
         ("signal", int),
         ("blocked", int),
         ("sigignore", int),
         ("sigcatch", int),
         ("wchan", int),
         ("nswap", int),
         ("cnswap", int),
         ("exit_signal", int),
         ("processor", int),]

colours = ['b', 'g', 'r', 'c', 'm', 'y']

def collectData(pid, task):
	"""
	Collect process list
	@param pid String

	"""
	f1 = open("/proc/%d/task/%s/stat"%(pid,task))
	f2 = open("/proc/%d/task/%s/statm"%(pid,task))
	t = datetime.datetime.now()
	stat = f1.readline().split()
	mem = f2.readline().split()
	d = dict([(name[0], name[1](el)) for (name, el) in zip(names, stat)])
	d["pmem"] = float(mem[1])

	return t, d

def getTime(key):
	"""
	Returns the time in microseconds
	"""
	return (((key.weekday() * 24 + key.hour) * 60 + key.minute) * 60 + key.second) * 1000000 + key.microsecond
  
class MonitorThread(threading.Thread):
	"""
	The monitor thread saves the process info every 10 seconds. Log is appended to so that
	same command line app can be tested with different parameters.  All associated threads
	will be reported on as "thread_id" under parent process of "process_id".

	Logged time within each call is relative to call start, so we can see when offset time
	of subordinate threads occurs.  Time is in millionths of a second.	Memory is in Kb

	@param label label to identify a particular call by.
	
	"""
	def __init__(self, pid, label):
		import collections

		self.label = label
		self.pid = pid
		threading.Thread.__init__(self)
		self.data = collections.defaultdict(dict)
		self.process = True
    
	def run(self):
		import os
		import time

		starttime = getTime( datetime.datetime.now())

		if not os.path.isfile('analyze.log'):
			with open('analyze.log', 'w') as logfile: 
				logger = csv.writer(logfile, delimiter = '	')
				logger.writerow(['time','command','call','process_id','thread_id','memory','cpu'])

		#line buffered write, otherwise you won't see log results for minutes
		with open('analyze.log', 'ab', 1) as logfile: 
			logger = csv.writer(logfile, delimiter = '	')

			while self.process:
				threads = os.listdir("/proc/%d/task/" % self.pid)
				sorted(threads, key=lambda x: (int(re.sub('\D','',x)),x)) #re strips non-digits

				for thread in threads: # string format of integer
					t, d = collectData(self.pid, thread)
					d["current_time"] = t
					logtime = getTime(t)

					#if thread == self.pid #overall memory plot should be 1 of the series.

					# "now" exists to fetch data from previous data item of EACH thread.
					if "now" in self.data[thread]:
						now = self.data[thread]["now"]
						d['pcpu'] = int( 1e6 * ((d['utime'] + d['stime']) - (now['utime'] + now['stime'])) / float((logtime - getTime(now["current_time"]))) )

						difftime = logtime - starttime
						row = [difftime, d['comm'], self.label, self.pid, int(thread), int(d['pmem']), d['pcpu']]
						logger.writerow(row)
						print row

					#to store entries in memory:
					#self.data[thread][getTime(t)] = d
					#make this available as previous record
					self.data[thread]["now"] = d

				time.sleep(10)


if __name__ == "__main__":
  """
	@param 1: label for using in "command"
    @param 2... : command to execute

  """
  import sys
  import os

  process = subprocess.Popen(sys.argv[2:])
  
  thread = MonitorThread(process.pid, sys.argv[1])
  thread.start()
  process.wait() # Wait until process has finished.
  thread.process = False
  thread.join()
  
