# Medusa Watcher, a very simple status info visualizer (useful for debugging)
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

import sys
import os
import socketio
import datetime
import pprint
import time
import json

def clear() : os.system('cls' if os.name == 'nt' else 'clear')

sio = socketio.Client()
ctx = {}

def print_header() : 
	print("medusa-watch (" + str(datetime.datetime.now()) + ") : " + ctx['server_addr'] + ":" + str(ctx['server_port']))

@sio.event(namespace="/medusabroadcaster")
def status_update(status_info):
	clear()
	print_header()
	pprint.pprint(status_info) # TODO : better display

if __name__ == "__main__" :
	ctx['server_addr'] = "http://localhost"
	ctx['server_port'] = 1877
	
	for i in range(len(sys.argv)) : 
		if sys.argv[i] == "-u" or sys.argv[i] == "--server-url" :   ctx['server_addr'] = sys.argv[i+1]
		if sys.argv[i] == "-p" or sys.argv[i] == "--server-port" :  ctx['server_port'] = int(sys.argv[i+1])
	
	sio.connect("http://localhost:1877", namespaces=["/medusabroadcaster"])
	sio.wait()
#	while True :
#		time.sleep(1)
#		sio.emit("poll_status_info", namespace="/medusabroadcaster")
		