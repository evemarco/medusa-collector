# Medusa Collector server
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

# internal dependencies
from MedusaStatusInfo import make_status_info
from MedusaParser import MedusaParser, recursive_merge
from MedusaGameTime import GameTime
from MedusaWorker import MedusaWorkerThread

# system and os
import sys


# time management
import datetime
import time

# concurrency management
import queue
import subprocess
import threading

# web app setup and networking
import socketio
import eventlet
#from aiohttp import web

# output and formatting
import json
import pprint

# monkeypatch
eventlet.monkey_patch()


# MedusaBroadcaster class-based namespace and event handlers
# Broadcasts status_info updates whenever they become available through calling broadcast_status_info.
# The provided status_info is emited for any socketio client connected to the MedusaBroadcaster instance.
class MedusaBroadcaster(socketio.Namespace) :
	
	def on_connect(self, sid, environ):
		print("MedusaBroadcaster : " + str(sid) + " connected")
	def on_disconnect(self, sid):
		print("MedusaBroadcaster : " + str(sid) + " disconnected")
	
	# broadcast a json dump of provided status_info to all clients connected to this namespace
	def broadcast_status_info(self, sid, status_info) :
		self.status_info = status_info
		# send status info to every subscriber
		if self.debug : print("broadcast_status_info : broadcasting status info")
		self.emit("status_update", status_info)

	def on_status_update(self, sid, status_info) :
		if debug : print ("LOL i got a status update event, and i'm the server !")

	def __init__(self, debug = False) :
		super().__init__('/medusabroadcaster')
		self.debug = debug
		

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
	def on_log_entries_col(self, sid, col) :
		if self.debug : print("on_log_entries_col : recieved new collection : ")
		if self.debug : pprint.pprint(col)
		# queue recieved log entries
		self.shared_recv_queue.put(col)
		
	# 'strmsg' event handler
	def on_strmsg(self, sid, msg) :
		print("MedusaServer : got message from " + self.connected_clients[sid].client_name + " : " + msg)
	
	def __init__(self, shared_recv_queue, debug = False):
		super().__init__('/medusacollector')
		self.shared_recv_queue = shared_recv_queue
		self.debug = debug



class MedusaServer :

	def serve(self) :
		# start main service thread using eventlet as a straightforward wsgi
		print("MedusaServer : service starting up on thread " +  str(threading.get_ident()))
		eventlet.wsgi.server(eventlet.listen((self.bind_addr, self.bind_port)), self.webapp)
		#web.run_app(self.webapp, host = self.bind_addr, port = self.bind_port)

	
	def __init__(self, bind_addr = "0.0.0.0", bind_port = 1877, redis_addr = 'localhost', redis_port=6379, replay_logs_output_filename = None, log_entries_persistance_duration = 15, debug = False) :
		print ("New MedusaServer")
		self.debug = debug
		self.eve_time_timedelta = None

		self.shared_recv_queue = queue.Queue()
		
		# init redis manager
		self.redis_addr = redis_addr
		self.redis_port = redis_port
		redis_target = 'redis://'
		redis_target += redis_addr
		if redis_port is not None : redis_target += ":" + str(redis_port)
		self.redis_manager = socketio.RedisManager(redis_target)

		# init socketio server
		self.bind_addr = bind_addr
		self.bind_port = bind_port
		self.socketio_server = socketio.Server(client_manager = self.redis_manager, logger=debug)
		
		# init broadcaster namespace
		self.broadcaster = MedusaBroadcaster()
		self.socketio_server.register_namespace(self.broadcaster)
		
		# start worker process
		self.worker_thread = threading.Thread(target=MedusaWorkerThread, args=(self.shared_recv_queue, str(self.redis_addr), str(self.redis_port)), kwargs={"debug":self.debug})
		self.worker_thread.daemon = True
		self.worker_thread.start()
		
		# init collector namespace
		self.collector = MedusaCollector(self.shared_recv_queue)
		self.socketio_server.register_namespace(self.collector)
		
		# init webapp
		#self.webapp = web.Application()
		#self.socketio_server.attach(self.webapp)
		self.webapp = socketio.WSGIApp(self.socketio_server)

		
	

if __name__ == "__main__" :
	callargs = []
	callargs.append("python")
	callargs.append(sys.argv[0].replace("MedusaServer.py", "Medusa.py"))
	callargs.append("-s")
	callargs += sys.argv[1:]
	subprocess.call(callargs, stdin = sys.stdin, stdout = sys.stdout, stderr = sys.stderr)
