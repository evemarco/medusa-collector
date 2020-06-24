#! /usr/bin/env python3

# Medusa Collector client and server
# This file is a part of the Medusa  project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

import sys
import os
import socketio
import socket
import eventlet
import queue
import threading
import datetime
import time
import platform
import json
import pprint
import re
from medusa_parser import log_entries_parser

# generic recursive merge function
def recursive_merge(src, dest) :
	if src is None : return
	try : # dict merge
		for k in src.keys() :
			if not k in dest.keys() :
				dest[k] = src[k]
			else :
				recursive_merge(src[k], dest[k])
	except AttributeError :
		try : # list merge
			dest.extend(src)
		except : 
			print("MedusaServer : recursive_merge Error : could not merge non-dict src into dest : \n  src = " + str(src) + "\n dest = " + str(dest))
			raise
	except : 
		print("MedusaServer : recursive_merge Error : could not merge non-dict src into dest : \n  src = " + str(src) + "\n dest = " + str(dest))
		raise



class MedusaClient :
	watch_loop_sleep_time = 1
	send_loop_sleep_time = 1
	refresh_watchers_loop_sleep_time = 30
	# sender thread
	
	def make_entries_collection(self) :
		r = {}
		while True : 
			try : recursive_merge(self.log_entries_queue.get(block = False), r)
			except queue.Empty :
				break
		if r == {} : return None
		#if self.debug : print("make_entries_collection : ready to send next entry collection : ")
		#if self.debug : pprint.pprint(r)
		return r
	
	def send_loop(self) :
		print("thread " + str(threading.get_ident()) + " entering send loop. MedusaClient.send_loop_sleep_time = " + str(MedusaClient.send_loop_sleep_time))
		while True :
			payload = self.make_entries_collection();
			if payload is not None :
				#if self.debug : print("send_loop : sending collected log entries : ")
				#if self.debug : pprint.pprint(payload)
				self.socketio_client.emit("log_entries_col", json.dumps(payload))
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
					m = re.match(r"(\[(?P<session_owner>(\w+ ?)+)\])?\s?" + log_entries_parser.re_time + "(?P<log_str>.*)", l)
					if m is None : 
						print("could not read session replay line : \n" + l)
						continue
					gdict = m.groupdict()
					if gdict["session_owner"] is None : 
						parser = log_entries_parser(gdict["Unknown"], self.debug)
					else :
						parser = log_entries_parser(gdict["session_owner"], self.debug)
					log_entry_time = log_entries_parser.time_str_to_datetime(gdict['time_str'])
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
		f = open(fname, "r")
		session_owner = self.parse_session_owner(f)
		if session_owner is None : 
			print("could not find session owner. Ignoring file")
			return None
		else : print ("found session owner : " + session_owner)
		parser = log_entries_parser(session_owner, self.debug)
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
			gamelogs_dir_path = os.path.join(d, "Gamelogs")
			flist = os.listdir(gamelogs_dir_path)
			flist = list(filter(lambda x : x.endswith('.txt'), flist)) # filter .txt files
			yesterday = datetime.datetime.now() - datetime.timedelta(days = 1)
			time_filter_comp = "{:04}{:02}{:02}_{:02}{:02}{:02}.txt".format( yesterday.year, yesterday.month, yesterday.day, yesterday.hour, yesterday.minute, yesterday.second )
			flist = list(filter(lambda x : x > time_filter_comp, flist)) # filter files that are les than 24h old
			if self.debug : print("found " + str(len(flist)) + " files that are less than 24h old")
			r = r + [os.path.join(gamelogs_dir_path, x) for x in flist]
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
	
	def __init__(self, server_addr = "localhost", server_port = 1877, replay_filename = None, debug = False) :
		print ("New MedusaClient")
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
		self.socketio_client.connect(target)
		print ("MedusaClient : connected to " + target)
		
		self.setup_send_loop_thread()
		
	
	def __del__(self) :
		self.socketio_client.disconnect()

class MedusaServer :
	
	class ClientInfo :
		def __init__(self, sid, client_name) :
			self.sid = sid
			self.client_name = client_name
			self.event_count = 0
			self.client_collections = [] # all collections recieved from this client
			print("MedusaServer : new client : " + self.client_name)
			
	
	# 'connect' event handler
	def connect(self, sid, environ) : 
		self.connected_clients_lock.acquire()
		self.connected_clients[sid] = self.ClientInfo(sid, str(self.socketio_server.get_session(sid)))
		self.connected_clients_lock.release()
	
	# 'disconnect' event handler
	def disconnect(self, sid) :
		self.connected_clients_lock.acquire()
		cinfo = self.connected_clients[sid]
		self.connected_clients_lock.release()
		self.disconnected_clients_lock.acquire()
		self.disconnected_clients[sid] = cinfo
		self.disconnected_clients_lock.release()
		print("MedusaServer : client disconnected : " + cinfo.client_name)
	
	# 'strmsg' event handler
	def strmsg(self, sid, msg) :
		print("MedusaServer : got message from " + self.connected_clients[sid].client_name + " : " + msg)
	
	
	# 'log_entries_col' event handler
	def log_entries_col(self, sid, payload) :
		payload = json.loads(payload)
		cinfo = self.connected_clients[sid]
		cinfo.client_collections.append(payload)
		cinfo.event_count += 1
		
		# merge new log entries
		self.log_entries_recv_queue.put(payload)
	
	def serve(self) :
		# start main service thread using eventlet as a straightforward wsgi
		print("MedusaServer : service starting up on thread " +  str(threading.get_ident()))
		eventlet.wsgi.server(eventlet.listen((self.bind_addr, self.bind_port)), self.web_app)
	
	def dump_collection(self, output_stream = None) :
		pprint.pprint(self.main_collection, output_stream)
	
	def dump_collection_debug_loop(self) :
		print("thread " + str(threading.get_ident()) + " entering collection dump loop. self.dump_collection_timer = " + str(self.dump_collection_timer))
		while True :
			time.sleep(self.dump_collection_timer)
			with open("collection_dump.txt", "w") as o:
				self.dump_collection(o)
	
	def setup_dump_collection_debug_loop_thread(self) :
		t = threading.Thread(target = self.dump_collection_debug_loop, name = "dump_collection_debug_loop")
		t.daemon = True
		t.start()

	# make status information
	def make_status_info(self) :
		status_info = {}
		status_info["characters"] = {}
		status_info["total"] = {
			'dps_in': 0,
			'dps_out': 0,
			'neut_in' : 0,
			'neut_out' : 0,
			'nos_in' : 0,
			'nos_out' : 0,
			'reps_in' : 0,
			'reps_out' : 0,
			'cap_transfer_in' : 0,
			'cap_transfer_out' : 0
		}
		
		def add_ship_type(status_info, pilot, ship_type) : 
			if ship_type is not None :
				status_info['characters'][pilot]["ship_type"] = ship_type

		# dps and alpha
		
		def add_damage(status_info, src_pilot, target_pilot, weapon_damage) :
			weapon_damage = int(weapon_damage)
			if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
			if not 'dps_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['dps_out'] = 0
			status_info['characters'][src_pilot]['dps_out'] += weapon_damage / self.dps_estimate_sliding_range
			if not 'alpha_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['alpha_out'] = 0
			status_info['characters'][src_pilot]['alpha_out'] = max(status_info['characters'][src_pilot]['alpha_out'], weapon_damage)
			
			if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
			if not 'dps_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['dps_in'] = 0
			status_info['characters'][target_pilot]['dps_in'] += weapon_damage / self.dps_estimate_sliding_range
			if not 'alpha_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['alpha_in'] = 0
			status_info['characters'][target_pilot]['alpha_in'] = max(status_info['characters'][target_pilot]['alpha_in'], weapon_damage)
		
		if 'dps' in self.main_collection:
			# dps out
			if 'weapon_cycle_out' in self.main_collection['dps'] :
				for e in self.main_collection['dps']['weapon_cycle_out'] :
					add_damage(status_info, e["session_owner"], e["target_pilot"], e["weapon_damage"])
					add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					status_info['total']['dps_out'] += int(e['weapon_damage']) / self.dps_estimate_sliding_range
			
			# dps in
			if 'weapon_cycle_in' in self.main_collection['dps'] : 
				for e in self.main_collection['dps']['weapon_cycle_in'] :
					add_damage(status_info, e["src_pilot"], e["session_owner"], e["weapon_damage"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['dps_in'] += int(e['weapon_damage']) / self.dps_estimate_sliding_range
		
		def add_neut(status_info, src_pilot, target_pilot, neut_amount) :
			neut_amount = int(neut_amount)
			if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
			if not 'neut_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['neut_out'] = 0
			status_info['characters'][src_pilot]['neut_out'] += neut_amount / self.dps_estimate_sliding_range

			if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
			if not 'neut_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['neut_in'] = 0
			status_info['characters'][target_pilot]['neut_in'] += neut_amount / self.dps_estimate_sliding_range
		
		def add_nos(status_info, src_pilot, target_pilot, nos_amount) :
			nos_amount = int(nos_amount)
			if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
			if not 'nos_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['nos_out'] = 0
			status_info['characters'][src_pilot]['nos_out'] += nos_amount / self.dps_estimate_sliding_range

			if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
			if not 'nos_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['nos_in'] = 0
			status_info['characters'][target_pilot]['nos_in'] += nos_amount / self.dps_estimate_sliding_range

		if 'neut' in self.main_collection:
			if 'neut_out' in self.main_collection['neut'] :
				for e in self.main_collection['neut']['neut_out'] :
					add_neut(status_info, e["session_owner"], e["target_pilot"], e["neut_amount"])
					add_ship_type(status_info, e["target_pilot"], e["target_ship_type"])
					status_info['total']['neut_out'] += int(e['neut_amount']) / self.dps_estimate_sliding_range
			if 'neut_in' in self.main_collection['neut'] :
				for e in self.main_collection['neut']['neut_in'] :
					add_neut(status_info, e["src_pilot"], e["session_owner"], e["neut_amount"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['neut_in'] += int(e['neut_amount']) / self.dps_estimate_sliding_range
			
			if 'nos_out' in self.main_collection['neut'] :
				for e in self.main_collection['neut']['nos_out'] :
					add_nos(status_info, e["session_owner"], e["target_pilot"], e["nos_amount"])
					add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					status_info['total']['nos_out'] += int(e['nos_amount']) / self.dps_estimate_sliding_range
			if 'nos_in' in self.main_collection['neut'] :
				for e in self.main_collection['neut']['nos_in'] :
					add_nos(status_info, e["src_pilot"], e["session_owner"], e["nos_amount"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['nos_in'] += int(e['nos_amount']) / self.dps_estimate_sliding_range
				
		
		# remote repair
		def add_remote_repair(status_info, src_pilot, target_pilot, repair_amount) :
			repair_amount = int(repair_amount)
			if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
			if not 'hps_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['hps_out'] = 0
			status_info['characters'][src_pilot]['hps_out'] += repair_amount / self.dps_estimate_sliding_range
			if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
			if not 'hps_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['hps_in'] = 0
			status_info['characters'][target_pilot]['hps_in'] += repair_amount / self.dps_estimate_sliding_range
		
		def add_remote_capacitor(status_info, src_pilot, target_pilot, energy_amount) :
			energy_amount = int(energy_amount)
			if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
			if not 'remote_capacitor_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['remote_capacitor_out'] = 0
			status_info['characters'][src_pilot]['remote_capacitor_out'] += energy_amount / self.dps_estimate_sliding_range
			if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
			if not 'remote_capacitor_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['remote_capacitor_in'] = 0
			status_info['characters'][target_pilot]['remote_capacitor_in'] += energy_amount / self.dps_estimate_sliding_range
		
		# remote repair out
		if 'remote_assist' in self.main_collection : 
			if 'remote_shield_out' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_shield_out'] :
					add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_shield_amount"])
					add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					status_info['total']['reps_out'] += int(e['remote_shield_amount']) / self.dps_estimate_sliding_range
			if 'remote_shield_in' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_shield_in'] :
					add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_shield_amount"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['reps_in'] += int(e['remote_shield_amount']) / self.dps_estimate_sliding_range
			
			if 'remote_armor_out' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_armor_out'] :
					add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_armor_amount"])
					add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					status_info['total']['reps_out'] += int(e['remote_armor_amount']) / self.dps_estimate_sliding_range
			if 'remote_armor_in' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_armor_in'] :
					add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_armor_amount"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['reps_in'] += int(e['remote_armor_amount']) / self.dps_estimate_sliding_range
			
			if 'remote_hull_out' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_hull_out'] :
					add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_hull_amount"])
					add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					status_info['total']['reps_out'] += int(e['remote_hull_amount']) / self.dps_estimate_sliding_range
			if 'remote_hull_in' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_hull_in'] :
					add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_hull_amount"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['reps_in'] += int(e['remote_hull_amount']) / self.dps_estimate_sliding_range
			
			if 'remote_capacitor_out' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_capacitor_out'] :
					add_remote_capacitor(status_info, e["src_pilot"], e["target_pilot"], e["energy_amount"])
					add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					status_info['total']['cap_transfer_out'] += int(e['energy_amount'])
			if 'remote_capacitor_in' in self.main_collection['remote_assist'] :
				for e in self.main_collection['remote_assist']['remote_capacitor_in'] :
					add_remote_capacitor(status_info, e["src_pilot"], e["target_pilot"], e["energy_amount"])
					add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
					status_info['total']['cap_transfer_in'] += int(e['energy_amount']) / self.dps_estimate_sliding_range
			
		
		# remote repair in
		# ignored since already accounted through remote repair_out as long as all logis use the client

		# ewar
		if 'ewar' in self.main_collection: 
			if 'scramble_attempt' in self.main_collection['ewar']:
				for e in self.main_collection['ewar']['scramble_attempt'] :
					if not e['target_pilot'] in status_info["characters"] : status_info['characters'][e['target_pilot']] = {}
					status_info['characters'][e['target_pilot']]["scrambled"] = True
					if "target_ship_type" in e : add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])

					if not e['src_pilot'] in status_info["characters"] : status_info['characters'][e['src_pilot']] = {}
					status_info['characters'][e['src_pilot']]["scrambling"] = True
					if "src_ship_type" in e : add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
			if 'disruption_attempt' in self.main_collection['ewar']:
				for e in self.main_collection['ewar']['disruption_attempt'] :
					if not e['target_pilot'] in status_info["characters"] : status_info['characters'][e['target_pilot']] = {}
					status_info['characters'][e['target_pilot']]["pointed"] = True
					if "target_ship_type" in e : add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
					if not e['src_pilot'] in status_info["characters"] : status_info['characters'][e['src_pilot']] = {}
					status_info['characters'][e['src_pilot']]["pointing"] = True
					if "src_ship_type" in e : add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
		
		return status_info
	
	def subscribe_to_status_infos(self, sid, request) :
		self.subscribers_lock.acquire()
		self.subscribers.append(sid)
		self.subscribers_lock.release()
		
	
	def broadcast_status_info(self, status_info) :
		print(json.dumps(status_info), file=open("status_info.json", "w"))
		# send status info to every subscriber
		self.subscribers_lock.acquire()
		for sid in self.subscribers : self.socketio_server.emit("status_update", json.dumps(status_info))
		self.subscribers_lock.release()
	
	def dump_replay_logs(self, col, replay_logs_output) :
		if self.replay_logs_output_filename is not None : 
			for e in col.values() : 
				for ee in e.values() : 
					for eee in ee : 
						print("[" + eee["session_owner"] + "]" + eee["log_str"], file=replay_logs_output)
	
	def get_least_evetime(self, col) :
		return max(list(map(lambda x : 
			max(list(map( lambda xx : 
				max(list(map( lambda xxx : log_entries_parser.time_str_to_datetime(xxx["time_str"])
				, xx)))
			, x.values())))
		, col.values())))
	
	def main_upkeep(self) :
		# empty recieve queue and populate main collection
		if self.debug : 
			print("entering main upkeep")
		now = datetime.datetime.now()
		replay_logs_output = None
		if self.replay_logs_output_filename is not None :
			try : 
				replay_logs_output = open(self.replay_logs_output_filename, "a")
			except : 
				"error : could not open file " + self.replay_logs_output_filename + " : " + sys.exc_info()[0] + ", disabling replay logs"
				self.replay_logs_output_filename = None
		while True :
			try :
				# print new entries for later replay
				col = self.log_entries_recv_queue.get(False)
				self.dump_replay_logs(col, replay_logs_output)
				if self.eve_time_timedelta is None : self.eve_time_timedelta = self.get_least_evetime(col) - now
				else : self.eve_time_timedelta = max(self.eve_time_timedelta, self.get_least_evetime(col) - now)
				if self.debug : 
					print("unpacking log entries collection : ")
					pprint.pprint(col)
				recursive_merge(col, self.main_collection)
				if self.debug : 
					with open("main_collection_after_rec_merge.txt", "w") as dbgout : pprint.pprint(self.main_collection, dbgout)
			except queue.Empty : break
		if self.replay_logs_output_filename is not None : replay_logs_output.close()
		
		# filter out old items from items collection
		if (self.eve_time_timedelta is not None) :
			lepd_dt = datetime.timedelta(seconds=self.log_entries_persistance_duration)
			persistance_limit = now + self.eve_time_timedelta - lepd_dt
		for k in self.main_collection.keys() : 
			for kk in self.main_collection[k].keys() : 
				self.main_collection[k][kk] = list(filter(lambda x : log_entries_parser.time_str_to_datetime(x["time_str"]) > persistance_limit, self.main_collection[k][kk]))

		if self.debug : 
			with open("main_collection_after_time_filter.txt", "w") as dbgout : pprint.pprint(self.main_collection, dbgout)

		status_info = self.make_status_info()
		with open("status_info_after_time_filter.txt", "w") as dbgout : pprint.pprint(status_info, dbgout)

		self.broadcast_status_info(status_info)
		
	def main_upkeep_loop(self) :
		print("thread " + str(threading.get_ident()) + " entering main upkeep loop. self.status_refresh_rate = " + str(self.status_refresh_rate))
		while True : 
			start = datetime.datetime.now()
			self.main_upkeep()
			end = datetime.datetime.now()
			sleeptime = self.status_refresh_rate - (end - start).total_seconds()
			if sleeptime > 0 : 
				time.sleep(sleeptime)
			else :
				print("Warning : seems like we are slower than target refresh rate here : main_upkeep took " + str((end - start).total_seconds()) + " seconds")
				time.sleep(1)
	def setup_main_upkeep_loop_thread(self) : 
		t = threading.Thread(target = self.main_upkeep_loop, name = "main_upkeep_loop")
		t.daemon = True
		t.start()

	def __init__(self, bind_addr = "localhost", bind_port = 1877, dump_collection_timer = None, replay_logs_output_filename = None, debug = False) :
		print ("New MedusaServer")
		self.debug = debug
		self.status_refresh_rate = 1
		self.log_entries_persistance_duration = 15
		self.dps_estimate_sliding_range = 15
		self.eve_time_timedelta = None
		self.dump_collection_timer = dump_collection_timer
		self.replay_logs_output_filename = replay_logs_output_filename

		self.connected_clients = {}
		self.connected_clients_lock = threading.Lock()
		self.disconnected_clients = {}
		self.disconnected_clients_lock = threading.Lock()
		
		self.subscribers = {}
		self.subscribers_lock = threading.Lock()
		
		self.main_collection = {}
		self.log_entries_recv_queue = queue.Queue()
		if (self.dump_collection_timer) : self.setup_dump_collection_debug_loop_thread()
		
		self.setup_main_upkeep_loop_thread()
		
		self.bind_addr = bind_addr
		self.bind_port = bind_port
		self.socketio_server = socketio.Server()
		self.socketio_server.on('connect', self.connect)
		self.socketio_server.on('disconnect', self.disconnect)
		self.socketio_server.on('strmsg', self.strmsg)
		self.socketio_server.on('log_entries_col', self.log_entries_col)
		self.socketio_server.on('subscribe_to_status_infos', self.subscribe_to_status_infos)
		self.web_app = socketio.WSGIApp(self.socketio_server)
		
	



if __name__ == "__main__" :

	client_server_addr = "http://localhost"
	client_server_port = 1877
	client_replay_filename = None

	server_mode = False
	server_bind_addr = "localhost"
	server_bind_port = 1877
	server_replay_logs_output_fname = None


	single_mode = False

	debug_mode = False # TODO : set default value to false



	for i in range(len(sys.argv)) : 
		if sys.argv[i] == "-u" or sys.argv[i] == "--server-url" : client_server_addr = sys.argv[i+1]
		if sys.argv[i] == "-p" or sys.argv[i] == "--server-port" : client_server_port = int(sys.argv[i+1])
		if sys.argv[i] == "-r" or sys.argv[i] == "--replay" : client_replay_filename = sys.argv[i+1]
		
		if sys.argv[i] == "-s" or sys.argv[i] == "--server" : server_mode = True
		if sys.argv[i] == "-b" or sys.argv[i] == "--server-bind-addr" : server_bind_addr = sys.argv[i+1]
		if sys.argv[i] == "-c" or sys.argv[i] == "--server-bind-port" : server_bind_port = int(sys.argv[i+1])
		if sys.argv[i] == "-f" or sys.argv[i] == "--replay-filename" : server_replay_logs_output_fname = sys.argv[i+1]
		
		if sys.argv[i] == "-1" or sys.argv[i] == "--single" : single_mode = True

		if sys.argv[i] == "-d" or sys.argv[i] == "--debug" : debug_mode = True


	print ("")
	print ("###### Welcome to Medusa ######")
	print ("")
	print ("-u <server address> or --server-url <server address> (" + client_server_addr + ") : server address to connect to (ignored for server mode)")
	print ("-p <port number> or --server-port <port number> (" + str(client_server_port) + ") : server port to connect to (ignored for server mode)")
	print ("-r <filename> for --replay <filename> (" + str(client_replay_filename) + ") : replay file instead of scanning for live game logs (ignored for server mode")
	print ("")
	print ("-s or --server (" + str(server_mode) + ") : run as server")
	print ("-b <server address> or --server-bind-addr <local address> (" + str(server_bind_addr) + ") : server address to bind to (ignored for client mode)")
	print ("-c <port number> or --server-bind-port <port number> (" + str(server_bind_port) + ") : server port to connect to (ignored for client mode)")
	print ("-f <filename> or --replay-filename <filename> (" + str(server_replay_logs_output_fname) + ") : write logs in profided filename for later replay")
	print ("")
	print ("-1 or --single (" + str(single_mode) + ") : run as client and server at the same time")
	print ("")
	print ("-d or --debug (" + str(debug_mode) + ") : various information, helpful for devs to diagnose bugs")
	print ("")
	print ("###############################")
	print ("")
	
	dump_collection_timer = None
	if debug_mode : dump_collection_timer = 5
	
	
	if single_mode : # program is both client and server
		server = MedusaServer(
			bind_addr = server_bind_addr,
			bind_port = server_bind_port,
			dump_collection_timer = dump_collection_timer,
			replay_logs_output_filename = server_replay_logs_output_fname,
			debug = debug_mode)
		threading.Thread(target=server.serve).start()
		client = MedusaClient(
			server_addr = client_server_addr,
			server_port = client_server_port,
			replay_filename = client_replay_filename,
			debug = debug_mode)
		client.run()
	else :
		if server_mode :
			server = MedusaServer(
				bind_addr = server_bind_addr,
				bind_port = server_bind_port,
				dump_collection_timer = dump_collection_timer,
				replay_logs_output_filename = server_replay_logs_output_fname,
				debug = debug_mode)
			server.serve()
		else :
			client = MedusaClient(
				server_addr = client_server_addr,
				server_port = client_server_port,
				replay_filename = client_replay_filename,
				debug = debug_mode)
			client.run()