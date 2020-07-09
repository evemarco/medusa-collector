# Medusa Worker process
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich																								 

from socket_io_emitter import Emitter
from MedusaGameTime import GameTime
import MedusaParser
from MedusaStatusInfo import make_status_info
import MedusaParser
import datetime
import sys
import queue
import threading
import time
import json
import pickle

# The MedusaWorker runs in its own process, poping logs collections from redis, and emiting status infos to the local MedusaServer as they become available.
class MedusaWorker :
	# pop a log collection items from the parent process (the medusa server)
	def get_next_logs_collection(self) :
		return server_pipe.recv()

	# send status info to the MedusaServer boradcaster service
	def send_status_info(self, status_info) :
		if self.debug : print("MedusaWorker sending new status info")
		print(json.dumps(status_info), file=open("status_info.json", "w"))
		
		#SINCE EMITTER IS BROKEN...
		# TODO : either replace socket_io_emitter with a working one, or just instanciate and use a redis client directly
		# self.socket_io_emitter.Emit("status_update", status_info)
		channel = "socketio"
		packet = {}
		packet['method'] = 'emit'
		packet['namespace'] = '/medusabroadcaster'
		packet['event'] = 'status_update'
		packet['data'] = status_info
		message = pickle.dumps( packet )
		self.socket_io_emitter._client.publish(channel, message)


	# dump log entries to File, open it if necessary
	def dump_replay_logs(self, col) :
		if self.replay_output_fname is None : return
		if self.replay_output is None :
			try :
				self.replay_output = open(self.replay_output_fname, "a")
			except :
				"error : could not open file " + self.replay_output_fname + " : " + sys.exc_info()[0] + ", disabling replay logs"
				self.replay_output_fname = None

		if replay_logs_output is not None :
			for e in col.values() :
				for ee in e.values() :
					for eee in ee :
						print("[" + eee["session_owner"] + "]" + eee["log_str"], file=replay_logs_output)

   	# returns the least evetime apprearing in logs entries contained in the provided log collections
	# useful for knowing roughly what is the actual time in eve, to the second-ish, based only on the logs recieved
	def get_least_evetime(self, col) :
		return max(list(map(lambda x : 
			max(list(map( lambda xx : 
				max(list(map( lambda xxx : GameTime.parse(xxx["time_str"], False)
				, xx)))
			, x.values())))
		, col.values())))
	

	# pop every log collection recieved by the local reciever thread, merge them into main collection
	# stop after timeout_datetime has come
	def merge_recv_loop(self, timeout_datetime) :
		while True :
			try : 
				col = self.shared_recv_queue.get_nowait()
			except queue.Empty :
				if datetime.datetime.now() > timeout_datetime : break
				time.sleep(0.2) # all work is done for now, we sure have time for a nap
				continue
			GameTime.update_ref(self.get_least_evetime(col))
			self.dump_replay_logs(col)
			MedusaParser.recursive_merge(col, self.main_collection)
			if datetime.datetime.now() > timeout_datetime : break



	# main worker loop, orchestrate the job of merging collected client logs, building status information and broadcasting it.
	def main_upkeep(self) :

		# empty recieve queue and populate main collection
		self.merge_recv_loop(datetime.datetime.now() + self.dt_status_refresh_period)

		# filter out events that are older than persistance
		persistance_limit = GameTime.now() - self.dt_persistance
		for k in self.main_collection.keys() :
			for kk in self.main_collection[k].keys() :
				self.main_collection[k][kk] = list(filter(lambda x : MedusaParser.MedusaParser.time_str_to_datetime(x["time_str"]) > persistance_limit, self.main_collection[k][kk]))

		# make status info from the remaining info
		status_info = make_status_info(self.main_collection, self.dps_window, GameTime.now())

		# broadcast new status info
		self.send_status_info(status_info)

	# loop over main upkeep
	def main_upkeep_loop(self) :
		print("thread " + str(threading.get_ident()) + " entering main upkeep loop. ")

		while True :
			start = datetime.datetime.now()
			self.main_upkeep()
			end = datetime.datetime.now()
			if self.debug : print("main_upkeep took " + str((end - start).total_seconds()) + " seconds")
			if end - start > 2*self.dt_status_refresh_period : 
				print("Warning : seems like we are slower than target refresh rate here : main_upkeep took " + str((end - start).total_seconds()) + " seconds")

	def __init__(self, shared_recv_queue, redis_host, redis_port, persistance = 15, dps_window = 15, replay_output_fname = None, status_refresh_period = 1, debug = False) :
		self.shared_recv_queue = shared_recv_queue
		self.redis_host = redis_host
		self.redis_port = redis_port
		self.dt_persistance = datetime.timedelta(seconds = persistance)
		self.dps_window = dps_window
		self.replay_output_fname = replay_output_fname
		self.dt_status_refresh_period = datetime.timedelta(seconds = status_refresh_period)
		self.debug = debug

		self.main_collection = {}
		self.replay_output = None
		self.recv_queue = queue.Queue()

		self.socket_io_emitter = Emitter({'host': self.redis_host, 'port': self.redis_port})
		print("MedusaWorker : Emitter connected to " + str(self.redis_host) + ":" + str(self.redis_port))
		self.main_upkeep_loop()


def MedusaWorkerThread(*args, **kwargs) :
	print("MedusaWorker online on thread " + str(threading.get_ident()))
	w = MedusaWorker(*args, **kwargs)
	w.main_upkeep_loop()
	