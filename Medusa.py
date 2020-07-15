#! /usr/bin/env python3

# Medusa Collector Main Executable for both client and server modes
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

# internal dependencies
from MedusaServer import MedusaServer
from MedusaClient import MedusaClient

# system and os
import sys

# concurrency management
import threading

# web app setup and networking
import socket

# if you want to compile to an exe file with pyinstaller, you must forece these prerequired
from eventlet.hubs import epolls, kqueue, selects
from dns import dnssec, e164, hash, namedict, tsigkeyring, update, version, zone

if __name__ == "__main__" :

	client_server_addr = "http://localhost"
	client_server_port = 1877
	client_replay_filename = None
	client_logs_dir_path = None

	server_mode = False
	server_bind_addr = "0.0.0.0"
	server_bind_port = 1877
	server_replay_logs_output_fname = None


	single_mode = False

	debug_mode = False # TODO : set default value to false
 

	for i in range(len(sys.argv)) :
		if sys.argv[i] == "-u" or sys.argv[i] == "--server-url" : client_server_addr = sys.argv[i+1]
		if sys.argv[i] == "-p" or sys.argv[i] == "--server-port" : client_server_port = int(sys.argv[i+1])
		if sys.argv[i] == "-l" or sys.argv[i] == "--logs-dir" : client_dir_path = sys.argv[i+1]
		if sys.argv[i] == "-r" or sys.argv[i] == "--replay" : client_replay_filename = sys.argv[i+1]
		if sys.argv[i] == "-l" or sys.argv[i] == "--logs-dir" : client_logs_dir_path = sys.argv[i+1]
		
		if sys.argv[i] == "-s" or sys.argv[i] == "--server" : server_mode = True
		if sys.argv[i] == "-b" or sys.argv[i] == "--server-bind-addr" : server_bind_addr = sys.argv[i+1]
		if sys.argv[i] == "-c" or sys.argv[i] == "--server-bind-port" : server_bind_port = int(sys.argv[i+1])
		if sys.argv[i] == "-f" or sys.argv[i] == "--replay-filename" : server_replay_logs_output_fname = sys.argv[i+1]
		
		if sys.argv[i] == "-1" or sys.argv[i] == "--single" : single_mode = True

		if sys.argv[i] == "-d" or sys.argv[i] == "--debug" : debug_mode = True

	if server_bind_addr == "auto" : server_bind_addr = socket.gethostname()
	
	
	print ("")
	print ("###### Welcome to Medusa ######")
	print ("")
	print ("-u <server address> or --server-url <server address> (" + client_server_addr + ") :\n\tserver address to connect to (ignored for server mode)")
	print ("-p <port number> or --server-port <port number> (" + str(client_server_port) + ") :\n\tserver port to connect to (ignored for server mode)")
	print ("-l <directory path> or --logs-dir <directory path> (" + str(client_logs_dir_path) + ") :\n\tpath to the Eve logs directory (ignored for server mode)")
	print ("-r <filename> for --replay <filename> (" + str(client_replay_filename) + ") :\n\treplay file instead of scanning for live game logs (ignored for server mode")
	print ("")
	print ("-s or --server (" + str(server_mode) + ") :\n\trun as server")
	print ("-b <local address> or --server-bind-addr <local address> (" + str(server_bind_addr) + ") :\n\tserver address to bind to (ignored for client mode)")
	print ("-c <port number> or --server-bind-port <port number> (" + str(server_bind_port) + ") :\n\tserver port to bind to (ignored for client mode)")
	print ("-f <filename> or --replay-filename <filename> (" + str(server_replay_logs_output_fname) + ") :\n\twrite logs in profided filename for later replay")
	print ("")
	print ("-1 or --single (" + str(single_mode) + ") :\n\trun as client and server at the same time")
	print ("")
	print ("-d or --debug (" + str(debug_mode) + ") :\n\tvarious information, helpful for devs to diagnose bugs")
	print ("")
	print ("###############################")
	print ("")
	
	
	if single_mode : # program is both client and server
		server = MedusaServer(
			bind_addr = server_bind_addr,
			bind_port = server_bind_port,
			replay_logs_output_filename = server_replay_logs_output_fname,
			debug = debug_mode)
		threading.Thread(target=server.serve).start()
		client = MedusaClient(
			client_logs_dir_path = client_logs_dir_path,
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
				replay_logs_output_filename = server_replay_logs_output_fname,
				debug = debug_mode)
			server.serve()
		else :
			client = MedusaClient(
				client_logs_dir_path = client_logs_dir_path,
				server_addr = client_server_addr,
				server_port = client_server_port,
				replay_filename = client_replay_filename,
				debug = debug_mode)
			client.run()