# Medusa Collector server
# This file is a part of the Medusa  project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

# internal dependencies
from MedusaStatusInfo import make_status_info
from MedusaParser import MedusaParser, recursive_merge

# system and os
import sys

# time management
import datetime
import time

# concurrency management
import queue
import threading

# web app setup and networking
import socketio
import eventlet

# output and formatting
import json
import pprint


# MedusaBroadcaster class-based namespace and event handlers
# Broadcasts status_info updates whenever they become available through calling broadcast_status_info.
# The provided status_info is emited for any socketio client connected to the MedusaBroadcaster instance.
class MedusaBroadcaster(socketio.Namespace) :
	
	def on_connect(self, sid, environ):
		print("MedusaBroadcaster : " + str(sid) + " connected")
	def on_disconnect(self, sid):
		print("MedusaBroadcaster : " + str(sid) + " disconnected")
	
	
	# broadcast a json dump of provided status_info to all clients connected to this namespace
	def broadcast_status_info(self, status_info) :
		self.status_info = status_info
		print(json.dumps(status_info), file=open("status_info.json", "w"))
		# send status info to every subscriber
		#self.emit("status_update", json.dumps(status_info))

	def on_poll_status_info(self, sid) :
		# send status info to requesting subscriber
		self.emit("status_update", json.dumps(self.status_info), room=sid)


# MedusaCollector class-based namespace and event handlers
# Connection and event reciever for collecting parsed log information.
# Instances of the MedusaClient connect to an instance of MedusaCollector to send parsed logs to the server
# Messages are entered in a shared recieve queue for later aggregation by the main upkeep loop
class MedusaCollector(socketio.Namespace) :
	def on_connect(self, sid, environ):
		print("MedusaCollector : " + str(sid) + " connected")
	def on_disconnect(self, sid):
		print("MedusaCollector : " + str(sid) + " disconnected")
	# 'log_entries_col' event handler
	def on_log_entries_col(self, sid, payload) :
		# parse message back to a dict
		payload = json.loads(payload)
		# queue recieved log entries
		self.log_entries_recv_queue.put(payload)
		
	# 'strmsg' event handler
	def on_strmsg(self, sid, msg) :
		print("MedusaServer : got message from " + self.connected_clients[sid].client_name + " : " + msg)
	
	def __init__(self, namespace):
		super().__init__(namespace)
		self.log_entries_recv_queue = queue.Queue()

class MedusaServer :
	
	def serve(self) :
		# start main service thread using eventlet as a straightforward wsgi
		print("MedusaServer : service starting up on thread " +  str(threading.get_ident()))
		eventlet.wsgi.server(eventlet.listen((self.bind_addr, self.bind_port)), self.web_app)
	
	def dump_replay_logs(self, col, replay_logs_output) :
		if self.replay_logs_output_filename is not None : 
			for e in col.values() : 
				for ee in e.values() : 
					for eee in ee : 
						print("[" + eee["session_owner"] + "]" + eee["log_str"], file=replay_logs_output)
	
	# returns the least evetime apprearing in logs entries contained in the provided log collections
	# useful for knowing roughly what is the actual time in eve, to the second-ish, based only on the logs recieved
	def get_least_evetime(self, col) :
		return max(list(map(lambda x : 
			max(list(map( lambda xx : 
				max(list(map( lambda xxx : MedusaParser.time_str_to_datetime(xxx["time_str"])
				, xx)))
			, x.values())))
		, col.values())))
	
	# main server loop, orchestrate the job of merging collected client logs, building status information and broadcasting it.
	def main_upkeep(self) :
		# empty recieve queue and populate main collection
		# filter out events that are older than log_entries_persistance_duration
		# make status info from the remaining info
		# broadcast new status info
		
		if self.debug : 
			print("entering main upkeep")
		now = datetime.datetime.now()
		replay_logs_output = None
		# make sure replay file is open if replay_logs_output_filename is set
		if self.replay_logs_output_filename is not None :
			try : 
				replay_logs_output = open(self.replay_logs_output_filename, "a")
			except : 
				"error : could not open file " + self.replay_logs_output_filename + " : " + sys.exc_info()[0] + ", disabling replay logs"
				self.replay_logs_output_filename = None
		# pop every log collection recieved by the local instance of MedusaCollector, merge them into main collection
		while True : 
			try :
				col = self.collector.log_entries_recv_queue.get(False) # non blocking pop operation (raises a queue.Empty if empty)
				# print new entries for later replay
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
				self.main_collection[k][kk] = list(filter(lambda x : MedusaParser.time_str_to_datetime(x["time_str"]) > persistance_limit, self.main_collection[k][kk]))

		if self.debug : 
			with open("main_collection_after_time_filter.txt", "w") as dbgout : pprint.pprint(self.main_collection, dbgout)

		status_info = make_status_info(self.main_collection, self.dps_estimate_sliding_range)
		
		with open("status_info_after_time_filter.txt", "w") as dbgout : pprint.pprint(status_info, dbgout)

		self.broadcaster.broadcast_status_info(status_info)
	
	
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

	def __init__(self, bind_addr = "localhost", bind_port = 1877, replay_logs_output_filename = None, debug = False) :
		print ("New MedusaServer")
		self.debug = debug
		self.status_refresh_rate = 1
		self.log_entries_persistance_duration = 15
		self.dps_estimate_sliding_range = self.log_entries_persistance_duration
		self.eve_time_timedelta = None
		self.replay_logs_output_filename = replay_logs_output_filename

		self.main_collection = {}
		
		
		self.bind_addr = bind_addr
		self.bind_port = bind_port
		self.socketio_server = socketio.Server()
		
		self.collector = MedusaCollector('/medusacollector')
		self.socketio_server.register_namespace(self.collector)
		self.broadcaster = MedusaBroadcaster('/medusabroadcaster')
		self.socketio_server.register_namespace(self.broadcaster)
		
		
		self.web_app = socketio.WSGIApp(self.socketio_server)
		
		self.setup_main_upkeep_loop_thread()
	

