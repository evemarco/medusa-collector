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
	
Using Command Line Arguments :

	-u <server address> or --server-url <server address> : server address to connect to (ignored for server mode)")
	-p <port number> or --server-port <port number> : server port to connect to (ignored for server mode)")
	-r <filename> for --replay <filename> : replay file instead of scanning for live game logs (ignored for server mode")

	-s or --server : run as server")
	-b <server address> or --server-bind-addr <local address> : server address to bind to (ignored for client mode)")
	-c <port number> or --server-bind-port <port number> : server port to connect to (ignored for client mode)")
	-f <filename> or --replay-filename <filename> : write logs in profided filename for later replay")

	-1 or --single : run as client and server at the same time")

	-d or --debug : various information, helpful for devs to diagnose bugs")

