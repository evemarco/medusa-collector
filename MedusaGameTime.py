# Medusa GameTime helper
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich


# Helper parser for game logs
# keeps track of game time based on ovserved timedelta between parsed dates from logs, allowing to predict what time is now on the server.
# Used to attach an in-game time generation date to the status_info object

import datetime

class GameTime :
	dt = None # the smallest timedelta observed between any server datetime and now

	# update dt if profided now - game_time is less than dt
	# use on any time you get from the ig logs to make sure we have the sharpest server time estimate
	# called automagically when parse is used
	# You can let the function call datetime.now or provide it yourself if you are calling a lot to avoid this overhead 
	@classmethod
	def update_ref(cls, game_time, now = datetime.datetime.now()) :
		tmp = datetime.datetime.now() - game_time
		if cls.dt is None or tmp < cls.dt : cls.dt = tmp

	@classmethod
	def time_str_to_datetime(cls, time_str) :
		return datetime.datetime.strptime(time_str,"%Y.%m.%d %H:%M:%S")
	
	@classmethod
	def parse(cls, str, update_ref = True) : # init from eve logs string
		tmp = cls.time_str_to_datetime(str)
		if update_ref : cls.update_ref(tmp)
		return tmp
	
	@classmethod
	def now(cls) :
		if cls.dt is None : return datetime.datetime.utcnow()
		return datetime.datetime.now() - cls.dt

	@classmethod
	def now_str(cls) : return cls.now().strftime("%Y.%m.%d %H:%M:%S")
