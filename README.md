# medusa-collector
Data collector parser, client and server for project MEdusa


Installing and First Use : 
	Medusa-collector is a collection of python3 sources, which can be run easily as usual python3 code.
	However, you will need to meet a couple of requirements :
	
	install the development python3 package :
		depending on the system you are running and the package manager you use, something like that should work
			sudo apt-get install python3-dev
	
	install the python-socketio package :
		pip3 install python-socketio
	install the eventlet package :
		pip3 install eventlet
	install the python redis client package :
		pip3 install redis
	install the python SocketIO Emitter package for redis :
		pip3 install socket.io-emitter

	Setting up the server :
		- Start up the redis server
		- navigate to the Medusa-Collector sources directory
		- start up the Medusa-Collector Server :
			python3 Medusa.py -s 
		or 
			python3 MedusaServer.py
		- start up the MedusaWatcher utility :
			python3 MedusaWatcher.py
		You should see a refreshing dated json dump of an object. 
		This is the structure emitted by the socketio server on the /medusabroadcaster namespace
		You can setup any sort of application or webclient to display this real-time information in any way you want.
		You can find our own version of the medusa web display on https://github.com/evemarco/medusa-web
		In order to connect to the server from another computer, 
		you will have to setup port opening and redirection from your firewall / provider. 
		Medusa-Collector uses port 1877 as a default
	Setting up the clients :
		- navigate to the Medusa-Collector sources directory
		- start up the Medusa-Collector client :
			python3 Medusa.py
		refer to the "Using Command Line Arguments" section below if your game logs are not located in a standard location
		In order to connect to the server from another computer, 
		you will need to provide the server and port the server is listening.
		


	
Using Command Line Arguments :

	-u <server address> or --server-url <server address> : server address to connect to (ignored for server mode)
	-p <port number> or --server-port <port number> : server port to connect to (ignored for server mode)
	-l <directory path> or --logs-dir <directory path> : path to the Eve logs directory (ignored for server mode)
		This option adds a directory in the list of system-dependant default 
		directory that the client will attempt to open in search for gamelogs files
		The provided directory should contain the Gamelogs directory (as opposed to being the Gamelogs directory itself)
	-r <filename> for --replay <filename> : replay file instead of scanning for live game logs (ignored for server mode)
		Placeholder : Not Yet Implemented

	-s or --server : run as server
	-b <local address> or --server-bind-addr <local address> : server address to bind to (ignored for client mode)
	-c <port number> or --server-bind-port <port number> : server port to bind to (ignored for client mode)
	-f <filename> or --replay-filename <filename> : write logs in profided filename for later replay
	
	-1 or --single : run as client and server at the same time

	-d or --debug : various information, helpful for devs to diagnose bugs

