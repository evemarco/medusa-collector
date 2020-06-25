
# Medusa Collector client
# This file is a part of the Medusa  project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

# internal dependencies
from MedusaParser import MedusaParser, recursive_merge

# system and os
import sys
import os
import platform

# time management
import datetime
import time

# concurrency management
import queue
import threading

# web app setup and networking
import socketio

# output and formatting
import json
import pprint
import re


class MedusaClient :
	watch_loop_sleep_time = 1
	send_loop_sleep_time = 1
	refresh_watchers_loop_sleep_time = 30
	# sender thread
	
	def make_entries_collection(self) :
		r = {}
		log_entries_count = 0
		while True : 
			try : 
				recursive_merge(self.log_entries_queue.get(block = False), r)
				log_entries_count += 1
			except queue.Empty :
				break
		if r == {} : return None
		if self.debug : print("make_entries_collection : ready to send next entry collection with " + str(log_entries_count) + " log entries")
		#if self.debug : pprint.pprint(r)
		return r
	
	def send_loop(self) :
		print("thread " + str(threading.get_ident()) + " entering send loop. MedusaClient.send_loop_sleep_time = " + str(MedusaClient.send_loop_sleep_time))
		while True :
			payload = self.make_entries_collection();
			if payload is not None :
				#if self.debug : print("send_loop : sending collected log entries : ")
				#if self.debug : pprint.pprint(payload)
				self.socketio_client.emit("log_entries_col", json.dumps(payload), namespace='/medusacollector')
			time.sleep(MedusaClient.send_loop_sleep_time)
	
	def setup_send_loop_thread(self) :
		t = threading.Thread(target=self.send_loop, name="send_loop")
		t.daemon = True
		t.start()
		return t
	
	# watcher thread
	
	def watch_loop(self, f, fname, parser) :
		print("thread " + str(threading.get_ident()) + " entering watch loop. MedusaClient.watch_loop_sleep_time = " + str(MedusaClient.watch_loop_sleep_time))
		while fname in self.watcher_threads :
			l = f.readline()
			if not l : 
				time.sleep(MedusaClient.watch_loop_sleep_time)
			else :
				if self.debug : print(l)
				self.log_entries_queue.put(parser.parse(l))
		f.close()
	
	def replay_file(self, fname) :
		print("thread " + str(threading.get_ident()) + " entering replay loop.")
		replay_speedup = 1
		replay_time = None
		with open(fname, "r", encoding='utf8') as f :
			while True :
				try : l = f.readline()
				except :
					"could not read line"
				if not l : break
				else :
					m = re.match(r"(\[(?P<session_owner>(\w+ ?)+)\])?\s?" + MedusaParser.re_time + "(?P<log_str>.*)", l)
					if m is None : 
						print("could not read session replay line : \n" + l)
						continue
					gdict = m.groupdict()
					if gdict["session_owner"] is None : 
						parser = MedusaParser(gdict["Unknown"], self.debug)
					else :
						parser = MedusaParser(gdict["session_owner"], self.debug)
					log_entry_time = MedusaParser.time_str_to_datetime(gdict['time_str'])
					if replay_time is None : replay_time = log_entry_time
					if replay_time > log_entry_time : #! TODO : do it better
						sleeptime = (log_entry_time - replay_time).total_seconds() / replay_speedup
						print ("sleeping for" + sleeptime)
						time.sleep(sleeptime)
					print("new line in replay file : " + l)
					self.log_entries_queue.put(parser.parse("[ " + gdict["time_str"] + " ]" + gdict["log_str"]))
	
	def parse_session_owner(self, f) :
		while True :
			l = f.readline()
			if not l : return None
			m = re.match(r"\s*Listener:\s*(?P<session_owner>(\w+ ?)+)", l)
			if m : 
				r = m.groupdict()["session_owner"]
				return r
		return None
	
	def setup_watch_loop_thread(self, fname) :
		print("setup_watch_loop_thread : " + fname)
		f = open(fname, "r", encoding='utf8')
		session_owner = self.parse_session_owner(f)
		if session_owner is None : 
			print("could not find session owner. Ignoring file")
			return None
		else : print ("found session owner : " + session_owner)
		parser = MedusaParser(session_owner, self.debug)
		f.seek(0,2)
		t = threading.Thread(target=self.watch_loop, name="watch_loop " + fname, args = (f,fname, parser))
		t.daemon = True
		t.start()
		return t
		return None
	
	# refresh watcher threads thread
	
	def get_log_file_path_list(self) :
		# look for eve online log files
		logs_dirs = []
		if self.client_dir_path is not None :
			logs_dirs.append(client_dir_path)
		r = []
		if platform.system() == "Darwin":
			# OS X
			# print ("detected OSX")
			logs_dirs.append("~/Library/Application Support/EVE Online/p_drive/User/My Documents/EVE")
		elif platform.system() == "Windows":
			# Windows...
			# print ("detected windows")
			logs_dirs.append(os.path.join(os.environ['USERPROFILE'], 'Documents', 'EVE', 'logs'))
		else :
			# Linux (or some close cousin)
			# print ("defaulted to linux")
			logs_dirs.append("~/Documents/EVE/logs/")
			logs_dirs.append("~/.local/share/Steam/steamapps/compatdata/8500/pfx/drive_c/users/steamuser/My Documents/EVE/logs")
		
		for d in logs_dirs :
			try : 
				gamelogs_dir_path = os.path.join(d, "Gamelogs")
				flist = os.listdir(gamelogs_dir_path)
				flist = list(filter(lambda x : x.endswith('.txt'), flist)) # filter .txt files
				yesterday = datetime.datetime.now() - datetime.timedelta(days = 1)
				time_filter_comp = "{:04}{:02}{:02}_{:02}{:02}{:02}.txt".format( yesterday.year, yesterday.month, yesterday.day, yesterday.hour, yesterday.minute, yesterday.second )
				flist = list(filter(lambda x : x > time_filter_comp, flist)) # filter files that are les than 24h old
				if self.debug : print("found " + str(len(flist)) + " files that are less than 24h old")
				r = r + [os.path.join(gamelogs_dir_path, x) for x in flist]
			except FileNotFoundError : 
				print("Warning directory not found : " + sys.exc_info()[1])
		if (len(r) == 0) : print("Warning : no game log files were found")
		return r
	
	def refresh_watchers(self) :
		filename_list = self.get_log_file_path_list()
		for f in filename_list :
			if not f in self.watcher_threads :
				self.watcher_threads[f] = True # because thread may startup and attempt to check if it is allowed to kepp running before the thread setup call returns the newly constructed thread object
				t = self.setup_watch_loop_thread(f)
				if t is not None : self.watcher_threads[f] = t
				else : del self.watcher_threads[f]
		for f in list(self.watcher_threads.keys()) :
			if not f in filename_list :
				del self.watcher_threads[f]
	
	def refresh_watchers_loop(self) : 
		print("thread " + str(threading.get_ident()) + " entering refresh watchers loop. MedusaClient.refresh_watchers_loop_sleep_time = " + str(MedusaClient.refresh_watchers_loop_sleep_time))
		while True : 
			self.refresh_watchers()
			time.sleep(MedusaClient.refresh_watchers_loop_sleep_time)
	
	def setup_refresh_watchers_loop_thread(self) : 
		t = threading.Thread(target=self.refresh_watchers_loop, name="refresh_watchers_loop ")
		t.daemon = True
		t.start()
		return t
	
	def run(self) :
		if self.replay_filename is not None : # replay mode
			self.replay_file(self.replay_filename)
		else :
			self.refresh_watchers_loop()
	
	def __init__(self, client_dir_path = None, server_addr = "localhost", server_port = 1877, replay_filename = None, debug = False) :
		print ("New MedusaClient")
		self.client_dir_path = client_dir_path
		self.debug = debug
		self.log_entries_queue = queue.Queue();
		self.watcher_threads = {}
		self.replay_filename = replay_filename
		
		self.server_addr = server_addr
		self.server_port = server_port
		self.socketio_client = socketio.Client()
		target = self.server_addr
		if self.server_port is not None : target += ":" + str(self.server_port)
		print ("MedusaClient : connecting to " + target)
		self.socketio_client.connect(target, namespaces=['/medusacollector'])
		print ("MedusaClient : connected to " + target)
		
		self.setup_send_loop_thread()
		
	
	def __del__(self) :
		self.socketio_client.disconnect()
