#! /usr/bin/env python3

# Medusa Collector Parser 
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich


# internal dependencies
from MedusaGameTime import GameTime

# time management
import datetime

# output and formatting
import re
import pprint



# generic recursive merge function :
# if dest and src are dicts, insert items to dest if key does not exist, merge recursively otherwise
# if dest and src are lists, extend dest with the items in src
def recursive_merge(src, dest) :
	if src is None : return
	try : # try dict merge
		for k in src.keys() :
			if not k in dest.keys() :
				dest[k] = src[k]
			else :
				recursive_merge(src[k], dest[k])
	except AttributeError :
		try : # try list merge
			dest.extend(src)
		except : # print out specific information and raise general error
			print("MedusaServer : recursive_merge Error : could not merge non-dict src into dest : \n  src = " + str(src) + "\n dest = " + str(dest))
			raise
	except : # print out specific information and raise general error
		print("MedusaServer : recursive_merge Error : could not merge non-dict src into dest : \n  src = " + str(src) + "\n dest = " + str(dest))
		raise

# parser function (dictates the entire server-side data layout)
class MedusaParser :

	re_time = r"\[ (?P<time_str>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) \]"
	def time_str_to_datetime(time_str) :
		return datetime.datetime.strptime(time_str,"%Y.%m.%d %H:%M:%S")

	re_entry_type = r"\(\w+\)"
	re_entry_type_combat = r"\((?P<entry_type>combat)\)"
	re_entry_type_notify = r"\((?P<entry_type>notify)\)"
	re_bold = r"<b>"
	re_nobold = r"</b>"
	re_color = r"<color=0x[0-9a-fA-F]{8}>"
	re_size = r"<font size=\d+>"
	re_nosize = r"</font>"
	re_name = r"((\w|-)+ ?)+"
	re_module_name = r"(\w+(-\w+)? ?)+"
	# type a src and target REs are for actors named in the following form : "Machariel [OSSB] HeWhoDaresWins " (such ase used for scramble attempts)
	# type b src and target REs are for actors named in the following form : "ShokuNaru[TRI.M](Drake)" (such as used for modules damage)
	re_src_type_a = r"((?P<src_you>you)|((?P<src_ship_type>" + re_name + r") (?P<src_alliance_ticker>&lt;" + re_name + r"&gt;)?(?P<src_corp_ticker>\[" + re_name + r"\]) (?P<src_pilot>" + re_name + r")))"
	re_src_type_b = r"(?P<src_pilot>" + re_name + r")(?P<src_alliance_ticker>&lt;" + re_name + r"&gt;)?(?P<src_corp_ticker>\[" + re_name + r"\])+\((?P<src_ship_type>" + re_name + r")\)"
	re_target_type_a = r"((?P<target_you>you)|((?P<target_ship_type>" + re_name + r") (?P<target_alliance_ticker>&lt;" + re_name + r"&gt;)?(?P<target_corp_ticker>\[" + re_name + r"\]) (?P<target_pilot>" + re_name + r")))"
	re_target_type_b = r"(?P<target_pilot>" + re_name + r")(?P<target_alliance_ticker>&lt;" + re_name + r"&gt;)?(?P<target_corp_ticker>\[" + re_name + r"\])+\((?P<target_ship_type>" + re_name + r")\)"
	re_weapon = r"- (?P<weapon>" + re_module_name + r")( - (?P<hit_type>" + re_name + r"))?"
	
	matching_rules = [] # a matching rule is a tuple of the form ("rule type", "rule name", re.compile(r"rule match"), result_object_build_function)

	# DAMAGE
	
	re_weapon_cycle_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<weapon_damage>\d+)" + re_nobold + " " + re_color + re_size + "to" + re_nosize + " " + re_bold + re_color + re_target_type_b + re_nobold + re_size + re_color + " " + re_weapon
	matching_rules.append(("dps", "weapon_cycle_out", re.compile(re_weapon_cycle_out)))
	re_weapon_cycle_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<weapon_damage>\d+)" + re_nobold + " " + re_color + re_size + "from" + re_nosize + " " + re_bold + re_color + re_src_type_b + re_nobold + re_size + re_color + " " + re_weapon
	matching_rules.append(("dps", "weapon_cycle_in", re.compile(re_weapon_cycle_in)))
	
	# [ 2020.06.23 13:08:48 ] (combat) <color=0xff7fffff><b>1800 GJ</b><color=0x77ffffff><font size=10> energy neutralized </font><b><color=0xffffffff>Armageddon &lt;XENA&gt;[BAG8] Raoul Abramovich </b><color=0x77ffffff><font size=10> - Standup Heavy Energy Neutralizer II</font>

	# CAPACITOR WARFARE

	# [ 2020.06.23 13:08:48 ] (combat) <color=0xffe57f7f><b>1800 GJ</b><color=0x77ffffff><font size=10> energy neutralized </font><b><color=0xffffffff>Fortizar [2MHS] J155002 - Baguette Launcher </b><color=0x77ffffff><font size=10> - Standup Heavy Energy Neutralizer II</font>
	re_neut_cycle_out = re_time + " " + re_entry_type_combat + " <color=0xff7fffff>" + re_bold + r"(?P<neut_amount>\d+) GJ" + re_nobold + re_color + re_size + " energy neutralized " + re_nosize + re_bold + re_color + re_target_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("neut", "neut_out", re.compile(re_neut_cycle_out)))
	re_neut_cycle_in = re_time + " " + re_entry_type_combat + " <color=0xffe57f7f>" + re_bold + r"(?P<neut_amount>\d+) GJ" + re_nobold + re_color + re_size + " energy neutralized " + re_nosize + re_bold + re_color + re_src_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("neut", "neut_in", re.compile(re_neut_cycle_in)))
	
#[ 2020.06.23 16:12:01 ] (combat) <color=0xff7fffff><b>+19 GJ</b><color=0x77ffffff><font size=10> energy drained from </font><b><color=0xffffffff>Dominix &lt;XENA&gt;[BAG8] Tnemelc Abramovich </b><color=0x77ffffff><font size=10> - Corpus X-Type Heavy Energy Nosferatu</font>
	re_nos_cycle_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"\+(?P<nos_amount>\d+) GJ" + re_nobold + re_color + re_size + " energy drained from " + re_nosize + re_bold + re_color + re_target_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("neut", "nos_out", re.compile(re_nos_cycle_out)))
#[ 2020.06.23 16:12:01 ] (combat) <color=0xffe57f7f><b>-19 GJ</b><color=0x77ffffff><font size=10> energy drained to </font><b><color=0xffffffff>Bhaalgorn &lt;XENA&gt;[BAG8] Raoul Abramovich </b><color=0x77ffffff><font size=10> - Corpus X-Type Heavy Energy Nosferatu</font>
	re_nos_cycle_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"-(?P<nos_amount>\d+) GJ" + re_nobold + re_color + re_size + " energy drained to " + re_nosize + re_bold + re_color + re_src_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("neut", "nos_in", re.compile(re_nos_cycle_in)))
	
	
	# EWAR
	
	re_scramble_attempt = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + "Warp scramble attempt" + re_nobold + " " + re_color + re_size + "from" + re_nosize + " " + re_color + re_bold + re_src_type_a + re_nobold + " " + re_color + re_size + "to " + re_bold + re_color + re_nosize + re_target_type_a
	matching_rules.append(("ewar", "scramble_attempt", re.compile(re_scramble_attempt)))
	
	re_disruption_attempt = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + "Warp disruption attempt" + re_nobold + " " + re_color + re_size + "from" + re_nosize + " " + re_color + re_bold + re_src_type_a + re_nobold + " " + re_color + re_size + "to " + re_bold + re_color + re_nosize + re_target_type_a
	matching_rules.append(("ewar", "disruption_attempt", re.compile(re_disruption_attempt)))

	# REMOTE ASSISTANCE

	re_remote_shield_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<remote_shield_amount>\d+)" + re_nobold + re_color + re_size + " remote shield boosted to " + re_nosize + re_bold + re_color + re_target_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_shield_out", re.compile(re_remote_shield_out)))
	re_remote_shield_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<remote_shield_amount>\d+)" + re_nobold + re_color + re_size + " remote shield boosted by " + re_nosize + re_bold + re_color + re_src_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_shield_in", re.compile(re_remote_shield_in)))
	
	re_remote_armor_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<remote_armor_amount>\d+)" + re_nobold + re_color + re_size + " remote armor repaired to " + re_nosize + re_bold + re_color + re_target_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_armor_out", re.compile(re_remote_armor_out)))
	re_remote_armor_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<remote_armor_amount>\d+)" + re_nobold + re_color + re_size + " remote armor repaired by " + re_nosize + re_bold + re_color + re_src_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_armor_in", re.compile(re_remote_armor_in)))
	
	re_remote_hull_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<remote_hull_amount>\d+)" + re_nobold + re_color + re_size + " remote hull repaired to " + re_nosize + re_bold + re_color + re_target_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_hull_out", re.compile(re_remote_hull_out)))
	re_remote_hull_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<remote_hull_amount>\d+)" + re_nobold + re_color + re_size + " remote hull repaired by " + re_nosize + re_bold + re_color + re_src_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_hull_in", re.compile(re_remote_hull_in)))
	
	re_remote_capacitor_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<energy_amount>\d+)" + re_nobold + re_color + re_size + " remote capacitor transmitted to " + re_nosize + re_bold + re_color + re_target_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_capacitor_out", re.compile(re_remote_capacitor_out)))
	re_remote_capacitor_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<energy_amount>\d+)" + re_nobold + re_color + re_size + " remote capacitor transmitted by " + re_nosize + re_bold + re_color + re_src_type_a + re_nobold + re_color + re_size + " " + re_weapon + re_nosize
	matching_rules.append(("remote_assist", "remote_capacitor_in", re.compile(re_remote_capacitor_in)))

	# COMMAND
	
	re_command_burst = re_time + " " + re_entry_type_notify + " " + re_bold + r"(?P<command_burst_type>)" + re_nobold + " has applied bonuses to " + re_bold + r"(?P<boosted_ships_count>\d+)" + re_nobold + " fleet members."
	matching_rules.append(("command", "command_burst", re.compile(re_command_burst)))
	
	# OTHERS
	
	re_timestamped_other = re_time
	#matching_rules.append(("other", "message", re.compile(re_timestamped_other)))
	
	
	# TODO : neut in and out
	
	def build_matched_log_entry(self, rule, match_result, log_str) :
		data = match_result.groupdict()
		data["log_str"] = log_str
		data["session_owner"] = self.session_owner #! TODO
		if rule[1].endswith("_in") : data["target_pilot"] = self.session_owner
		elif rule[1].endswith("_out") : data["src_pilot"] = self.session_owner
		elif "src_you" in data and data["src_pilot"] == None : data["src_pilot"] = self.session_owner
		elif "target_you" in data and data["target_pilot"] == None : data["target_pilot"] = self.session_owner
		for k in data.keys() : 
			if data[k] is not None : 
				data[k] = data[k].strip()
		return {rule[0] : {rule[1] : [data]}}
	
	def parse(self, log_entry_str) :
		if log_entry_str == None : return {}
		for rule in MedusaParser.matching_rules :
			m = rule[2].match(log_entry_str)
			if m is not None :
				r = self.build_matched_log_entry(rule, m, log_entry_str)
				if self.debug :
					print("matched rule " + rule[1] + " : ")
					pprint.pprint(r)
				return r
		return {}

	def __init__(self, session_owner, debug = False) :
		self.debug = debug
		self.session_owner = session_owner

if __name__ == "__main__" :
	parser = MedusaParser("Dummy McDum")
	with open("parser_test_logs.txt", "r") as f :
		for l in f.readlines() :
#			print("  --  new line  --\n" + l)
			entry_collection = parser.parse(l)
#			pprint.pprint(entry_collection)
#			print("\n")