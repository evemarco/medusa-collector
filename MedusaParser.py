#! /usr/bin/env python3

# Medusa Collector Parser 
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich


# internal dependencies
from MedusaGameTime import GameTime

import sys

# time management
import datetime

# output and formatting
import yaml
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



# basic construction blocks
re_time = r"\[ (?P<time_str>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) \]" # "[ 2020.07.09 11:35:20 ]"
def time_str_to_datetime(time_str) :
	return datetime.datetime.strptime(time_str,"%Y.%m.%d %H:%M:%S")
re_entry_type = r"\(\w+\)" # "(combat)" (generic)
re_entry_type_combat = r"\((?P<entry_type>combat)\)"  # "(combat)" (specific)
re_entry_type_notify = r"\((?P<entry_type>notify)\)"  # "(notify)" (specific)
re_bold = r"<b>"
re_nobold = r"</b>"
re_italic = r"<i>"
re_noitalic = r"</i>"
re_underline = r"<u>"
re_nounderline = r"</u>"
re_bold = r"<b>"
re_nobold = r"</b>"
re_color = r"<color=0x[0-9a-fA-F]{8}>"
re_nocolor = r"</color>"
re_size = r"<font size=\d+>"
re_nosize = r"</font>"
re_name = r"((\w|-)+ ?)+" # matches generic name with "-" that can either have space around them or not
re_module_name = r"(\w+(-\w+)? ?)+" # matches a module name with "-" that cannot have space around them (e.g "A-type Medium Remote Armor Repairer" or "Light Electron Blaster II", but not "Light Electron Blaster II - Hits")
re_weapon = r"((" + re_size + re_color + r")|(" + re_color + re_size + r"))" + r" - (?P<weapon>" + re_module_name + r")( - (?P<hit_type>" + re_name + r"))?(" + re_nosize + r")?"


# Agent Parser : handles the generation of regexp for parsing agents (src and target) given a supplied overview configuration file
# or from default presets as a late initialization
class AgentParser() :
	class LateInitException(Exception) :
		"""Exception : Agent Parser is not Initialized"""
		pass
	class InitFailException(Exception) :
		"""Exception : Agent Parser could not be initialized"""
		pass

	agent_pre = r"((" + re_bold + re_color + r")|(" + re_color + re_bold + r"))(" + re_nosize + r")?"
	agent_post = r"(" + re_nobold + r")?"
	# <b><color=0xffffffff>Tnemelc Abramovich[BAG8](Ishkur)</b>
	default_damage = re_bold + re_color + r"(?P<agent_pilot>" + re_name + r")(?P<agent_corp_ticker>\[" + re_name + r"\])?\((?P<agent_ship_type>" + re_name + r")\)" + re_nobold
	m_re_damage_src = default_damage.replace("agent", "src")
	m_re_damage_target = default_damage.replace("agent", "target")

	# "<color=0xffffffff><b>you</b>"
	# "<b><color=0xffffffff></font>you!"
	you_src = r"(?P<src_you>you)"
	you_target = r"(?P<target_you>you)!"

	# "Pilot [CC]" preset
	#<color=0xffffffff><b>Ishkur &lt;XENA&gt;[BAG8] Tnemelc Abramovich </b>
	preset1 = r"(?P<agent_ship_type>" + re_name + r") (&lt;(?P<agent_alliance_ticker>" + re_name + r")&gt;)?(\[(?P<agent_corp_ticker>" + re_name + r")\])? (?P<agent_pilot>" + re_name + r") "

	# "Pilot [CC AA]" preset
	#<color=0xffffffff><b>Tnemelc Abramovich [BAG8,XENA]</b>
	preset2 = r"(?P<agent_pilot>" + re_name + r") \[(?P<agent_corp_ticker>" + re_name + r")(,(?P<agent_alliance_ticker>" + re_name + r"))?\]"

	# "[CC] Pilot [AA]" preset
	#<color=0xffffffff><b> [BAG8]Tnemelc Abramovich&lt;XENA&gt;</b>
	preset3 = r" \[(P?<agent_corp_ticker>" + re_name + r")\](P?<agent_pilot>" + re_name + r")(&lt;(?P<agent_alliance_ticker>" + re_name + r")&gt;)?"

#	import MedusaParser; MedusaParser.AgentParser.get_LabelOrder_from_overview("C:\\Users\\Fontenaille\\Documents\\EVE\\Overview\\raoul_abramovich_2020-06-25.yaml")
	@classmethod
	def get_LabelOrder_from_overview(cls, from_overview_filename) :
		f = open(from_overview_filename, "r")
		y = yaml.load(f.read())
		labelOrder = y['shipLabelOrder']
		for i in range(len(labelOrder)) : # for each label element
			for j in range(len(y['shipLabels'])) : # look for corresponding item in shiplabels list
				if y['shipLabels'][j][0] == labelOrder[i] : # if found it
					labelOrder[i] = dict(y['shipLabels'][j][1]) # replace label element with the corresponding content
		#pprint.pprint(labelOrder)
		return labelOrder
	
	@classmethod
	def get_agent_re_elt_pre(cls, ov_param) :
		agent_re_pre = ""
		if ov_param['fontsize'] :
			agent_re_pre += re_size
		if ov_param['color'] :
			agent_re_pre += re_color
		agent_re_pre += ov_param['pre']
		if ov_param['italic'] :
			agent_re_pre += re_italic
		if ov_param['underline'] :
			agent_re_pre += re_underline
		if ov_param['bold'] :
			agent_re_pre += re_bold
		return agent_re_pre

	@classmethod
	def get_agent_re_elt_post(cls, ov_param) :
		agent_re_post = ""
		if ov_param['bold'] :
			agent_re_post += re_nobold
		if ov_param['underline'] :
			agent_re_post += re_nounderline
		if ov_param['italic'] :
			agent_re_post += re_noitalic
		agent_re_post += ov_param['post']
		if ov_param['color'] :
			agent_re_post += re_nocolor
		if ov_param['fontsize'] :
			agent_re_post += re_nosize
		return agent_re_post

	@classmethod
	def get_agent_re_elt(cls, ov_param) :
		# special cases
		if ov_param['type'] == 'linebrak' : # linebreaks translate into a single space
			print("found linebreak !")
			return ' '
		if ov_param['type'] == None and ov_param['state']: # None type is the "additionnal text", and does not trigger anything but printing pre, even if specified otherwise
			return r'(' + ov_param['pre'] + r')?'
		# other label elements
		r = ''
		r += AgentParser.get_agent_re_elt_pre(ov_param)
		if ov_param['type'] == 'corporation' :
			r += r"(?P<agent_corp_ticker>" + re_name + r")"
		if ov_param['type'] == 'pilot name' :
			r += r"(?P<agent_pilot>" + re_name + r")"
		if ov_param['type'] == 'alliance' :
			r += r"(?P<agent_alliance_ticker>" + re_name + r")"
		if ov_param['type'] == 'ship name' :
			r += r"(?P<agent_ship_name>" + re_name + r")"
		if ov_param['type'] == 'ship type' :
			r += r"(?P<agent_ship_type>" + re_name + r")"
		r += AgentParser.get_agent_re_elt_post(ov_param)
		if ov_param['type'] == 'corporation' or ov_param['type'] == 'alliance' :
			r = r'(' + r + r')?'
		return r

	@classmethod
	def labelOrder_to_agent_re(cls, labelOrder) :
		agent_re = ""
		for elt in labelOrder :
			agent_re += cls.get_agent_re_elt(elt)

	@classmethod
	def re_dmg_src(cls) :
		return AgentParser.m_re_damage_src
	@classmethod
	def re_dmg_target(cls) :
		return AgentParser.m_re_damage_target

	def re_src(self) :
		if self.is_init : return self.m_re_src
		raise AgentParser.LateInitException
	def re_target(self) :
		if self.is_init : return self.m_re_target
		raise AgentParser.LateInitException
		
	# Initialize an AgentParser object
	# Either supply an agent_re, e.g from AgentParser presets, or an overview config file (either full or relative path), or no arguments for later initialization
	# agent_str_example is an optional test string to check matching against when late initializing, raising InitFailException upon failing to match it
	def initialize(self, agent_re = None, agent_str_example = None, overview_filename = None) :
		#if agent_str_example is not None : print("AgentParser : late initialize attempt : \n  agent_re = " + agent_re + "\n  agent_str_example = " + agent_str_example)
		if overview_filename is not None :
			if self.debug : print("AgentParser : initializing from file " + overview_filename)
			agent_re = AgentParser.labelOrder_to_agent_re(AgentParser.get_LabelOrder_from_overview(overview_filename))
		if agent_re is not None :
			if agent_str_example is not None :
				if self.debug : print("AgentParser : attempting late initialization : ")
				testre = AgentParser.agent_pre + agent_re + AgentParser.agent_post
				if self.debug : print("testre = " + testre)
				if self.debug : print("agent_str_example = " + agent_str_example)
				m = re.match(testre, agent_str_example)
				if m is None : 
					print("AgentParser : late initialize attempt failed")
					raise AgentParser.InitFailException
			self.m_re_src = AgentParser.agent_pre + r"((" + AgentParser.you_src + r")|(" + agent_re.replace("agent", "src") + r"))" + AgentParser.agent_post
			self.m_re_target = AgentParser.agent_pre + r"((" + AgentParser.you_target + r")|(" + agent_re.replace("agent", "target") + r"))" + AgentParser.agent_post
			self.is_init = True
			if self.debug : print("AgentParser initialized")

	def __init__(self, agent_re = None, agent_str_example = None, overview_filename = None, debug = False) :
		self.debug = debug
		self.is_init = False
		self.initialize(agent_re, agent_str_example, overview_filename)


# parser function (dictates the entire server-side data layout)
class MedusaParser :
	class MatchingRuleDamage : # simple matching rule definition, used for parsing dps (which do not use overview-dependant formatting)
		def match(self, str) :
			#print("MatchingRuleDamage : attempting match :\n" + self.regexp_str + "\n" + str)
			return self.regexp.match(str)
		def __init__(self, regexp_str, category, rule_name) : 
			self.regexp_str = regexp_str
			self.regexp = re.compile(regexp_str)
			self.category = category
			self.rule_name = rule_name


	class MatchingRule : # matching rule definition, used for parsing log entries which use overview-dependant formatting
		# regexp_pattern is in the form ["azeaze", "agent_src", "zerzer", "agent_target", "ertert"]
		def __init__(self, regexp_pattern, category, rule_name, agent_parser = None, debug = False) : 
			self.regexp_pattern = regexp_pattern
			self.category = category
			self.rule_name = rule_name
			self.agent_parser = agent_parser
			self.debug = debug
			if agent_parser is None or agent_parser.is_init :
				self.init_regexp()
			else :
				self.init_test_regexp()

		def init_regexp(self) :
			self.regexp = r""
			for e in self.regexp_pattern :
				if e == "agent_src" : self.regexp += self.agent_parser.re_src()
				elif e == "agent_target" : self.regexp += self.agent_parser.re_target()
				else : self.regexp += e
			self.regexp_str = self.regexp
			self.regexp = re.compile(self.regexp)
			#print("MatchingRule : init_regexp : \n  " + self.regexp_str)

		def init_test_regexp(self) :
			self.test_regexp = r""
			for e in self.regexp_pattern :
				if e == "agent_src" : self.test_regexp += r"(?P<agent_src_test>.*)"
				elif e == "agent_target" : self.test_regexp += r"(?P<agent_target_test>.*)"
				else : self.test_regexp += e
			self.test_regexp_str = self.test_regexp
			#print("\nMatchingRule : init_regexp : \n" + self.test_regexp_str)
			self.test_regexp = re.compile(self.test_regexp)

		def match(self, str) :
			try :
				return self.regexp.match(str)
			except AttributeError :
				print("self.regexp.match(str) raised AttributeError : ")
				#pprint.pprint(sys.exc_info())
				pass
			# else try init regexp
			if self.agent_parser.is_init :
				print("agent_parser is initialized, just finalize initialization and retry")
				self.init_regexp()
				return self.match(str) # retry and return match
			# else try init agent_parser
			else :
				# make a test agent string to test default presets initializations against
				testm = self.test_regexp.match(str)
				if self.debug : print("attempting late agent parser initialization for rule " + self.rule_name)
				if not testm :
					return None # if failed, just return none, rule does not match anyway
				gd = testm.groupdict()
				teststr = gd['agent_src_test'] if 'agent_src_test' in gd else ( gd['agent_target_test'] if 'agent_target_test' in gd else None )
				if teststr is None : # we should never hit this condition unless ill-formed matching rules
					print("Whoops, maybe we should take a look into this : ")
					print("str = " + str)
					print("self.test_regexp = " + self.test_regexp)
					print("self.test_regexp.match().groupdict() : ")
					pprint.pprint(gd)
					return None
				try :
					self.agent_parser.initialize(agent_re = AgentParser.preset1, agent_str_example = teststr)
					return self.match(str) # retry and return match
				except AgentParser.InitFailException :
					pass
				try :
					self.agent_parser.initialize(agent_re = AgentParser.preset2, agent_str_example = teststr)
					return self.match(str) # retry and return match
				except AgentParser.InitFailException :
					pass
				try :
					self.agent_parser.initialize(agent_re = AgentParser.preset3, agent_str_example = teststr)
					return self.match(str) # retry and return match
				except AgentParser.InitFailException :
					pass
				print("Warning : default late initialization of matching rule " + self.category + ":" + self.rule_name + " failed at finding a working preset for matching string \"" + teststr + "\".")
				print("When attempting to match log entry : \n  \"" + str + "\"")
				print("Maybe you should supply an updated overview configuration file instead ?")
			return None

	def init_rules(self) :

		self.matching_rules = [] # a matching rule is a tuple of the form ("rule type", "rule name", re.compile(r"rule match"), result_object_build_function)

		# DAMAGE
	
		re_weapon_cycle_out = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<weapon_damage>\d+)" + re_nobold + " " + re_color + re_size + "to" + re_nosize + " " + AgentParser.re_dmg_target() + re_weapon
		self.matching_rules.append(MedusaParser.MatchingRuleDamage(re_weapon_cycle_out, "dps", "weapon_cycle_out"))
		re_weapon_cycle_in = re_time + " " + re_entry_type_combat + " " + re_color + re_bold + r"(?P<weapon_damage>\d+)" + re_nobold + " " + re_color + re_size + "from" + re_nosize + " " + AgentParser.re_dmg_src() + re_weapon
		self.matching_rules.append(MedusaParser.MatchingRuleDamage(re_weapon_cycle_in, "dps", "weapon_cycle_in"))
	
		# [ 2020.06.23 13:08:48 ] (combat) <color=0xff7fffff><b>1800 GJ</b><color=0x77ffffff><font size=10> energy neutralized </font><b><color=0xffffffff>Armageddon &lt;XENA&gt;[BAG8] Raoul Abramovich </b><color=0x77ffffff><font size=10> - Standup Heavy Energy Neutralizer II</font>

		# CAPACITOR WARFARE

		# [ 2020.06.23 13:08:48 ] (combat) <color=0xffe57f7f><b>1800 GJ</b><color=0x77ffffff><font size=10> energy neutralized </font><b><color=0xffffffff>Fortizar [2MHS] J155002 - Baguette Launcher </b><color=0x77ffffff><font size=10> - Standup Heavy Energy Neutralizer II</font>
		re_neut_cycle_out = [
			re_time + " " + re_entry_type_combat +
				" <color=0xff7fffff>" + re_bold + r"(?P<neut_amount>\d+) GJ" + re_nobold +
				re_color + re_size + " energy neutralized " + re_nosize,
			"agent_target",
			re_weapon
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_neut_cycle_out, "neut", "neut_out", self.agent_parser))

		re_neut_cycle_in = [
			re_time + " " + re_entry_type_combat +
				" <color=0xffe57f7f>" + re_bold + r"(?P<neut_amount>\d+) GJ" + re_nobold +
				re_color + re_size + " energy neutralized " + re_nosize,
			"agent_src",
			re_weapon
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_neut_cycle_in, "neut", "neut_in", self.agent_parser))
	
		#[ 2020.06.23 16:12:01 ] (combat) <color=0xff7fffff><b>+19 GJ</b><color=0x77ffffff><font size=10> energy drained from </font><b><color=0xffffffff>Dominix &lt;XENA&gt;[BAG8] Tnemelc Abramovich </b><color=0x77ffffff><font size=10> - Corpus X-Type Heavy Energy Nosferatu</font>
		re_nos_cycle_out = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"\+(?P<nos_amount>\d+) GJ" + re_nobold +
			re_color + re_size + " energy drained from " + re_nosize,
		   "agent_target",
			re_weapon
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_nos_cycle_out, "neut", "nos_out", self.agent_parser))
		#[ 2020.06.23 16:12:01 ] (combat) <color=0xffe57f7f><b>-19 GJ</b><color=0x77ffffff><font size=10> energy drained to </font><b><color=0xffffffff>Bhaalgorn &lt;XENA&gt;[BAG8] Raoul Abramovich </b><color=0x77ffffff><font size=10> - Corpus X-Type Heavy Energy Nosferatu</font>
		re_nos_cycle_in = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"-(?P<nos_amount>\d+) GJ" + re_nobold +
			re_color + re_size + " energy drained to " + re_nosize +
		   "agent_src",
			re_weapon
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_nos_cycle_in, "neut", "nos_in", self.agent_parser))
	
	
		# EWAR
	
		re_scramble_attempt = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + "Warp scramble attempt" + re_nobold +
			" " + re_color + re_size + "from" + re_nosize + " ",
			"agent_src",
			" " + re_color + re_size + "to ",
			"agent_target"
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_scramble_attempt, "ewar", "scramble_attempt", self.agent_parser))
	
		re_disruption_attempt = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + "Warp disruption attempt" + re_nobold +
			" " + re_color + re_size + "from" + re_nosize + " ",
			"agent_src",
			" " + re_color + re_size + "to " + 
			"agent_target"
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_disruption_attempt, "ewar", "disruption_attempt", self.agent_parser))

		# REMOTE ASSISTANCE

		re_remote_shield_out = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"(?P<remote_shield_amount>\d+)" + re_nobold +
			re_color + re_size + " remote shield boosted to " + re_nosize,
			"agent_target",
			re_weapon
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_shield_out, "remote_assist", "remote_shield_out", self.agent_parser))
		re_remote_shield_in = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"(?P<remote_shield_amount>\d+)" + re_nobold +
			re_color + re_size + " remote shield boosted by " + re_nosize,
			"agent_src",
			re_weapon
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_shield_in, "remote_assist", "remote_shield_in", self.agent_parser))
	
		re_remote_armor_out = [
			re_time + " " + re_entry_type_combat + " " + re_color +
			re_bold + r"(?P<remote_armor_amount>\d+)" + re_nobold +
			re_color + re_size + " remote armor repaired to " + re_nosize,
			"agent_target",
			re_color + re_size + " " + re_weapon + re_nosize
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_armor_out, "remote_assist", "remote_armor_out", self.agent_parser))
		re_remote_armor_in = [
			re_time + " " + re_entry_type_combat + " " + re_color +
			re_bold + r"(?P<remote_armor_amount>\d+)" + re_nobold +
			re_color + re_size + " remote armor repaired by " + re_nosize,
			"agent_src",
			re_color + re_size + " " + re_weapon + re_nosize
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_armor_in, "remote_assist", "remote_armor_in", self.agent_parser))
	
		re_remote_hull_out = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"(?P<remote_hull_amount>\d+)" + re_nobold +
			re_color + re_size + " remote hull repaired to " + re_nosize,
			"agent_target",
			re_color + re_size + " " + re_weapon + re_nosize
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_hull_out, "remote_assist", "remote_hull_out", self.agent_parser))
		re_remote_hull_in = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"(?P<remote_hull_amount>\d+)" + re_nobold +
			re_color + re_size + " remote hull repaired by " + re_nosize,
			"agent_src",
			re_color + re_size + " " + re_weapon + re_nosize
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_hull_in, "remote_assist", "remote_hull_in", self.agent_parser))
	
		re_remote_capacitor_out = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"(?P<energy_amount>\d+)" + re_nobold +
			re_color + re_size + " remote capacitor transmitted to " + re_nosize,
			"agent_target",
			re_color + re_size + " " + re_weapon + re_nosize
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_capacitor_out, "remote_assist", "remote_capacitor_out", self.agent_parser))
		re_remote_capacitor_in = [
			re_time + " " + re_entry_type_combat + " " +
			re_color + re_bold + r"(?P<energy_amount>\d+)" + re_nobold +
			re_color + re_size + " remote capacitor transmitted by " + re_nosize,
			"agent_src",
			re_color + re_size + " " + re_weapon + re_nosize
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_remote_capacitor_in, "remote_assist", "remote_capacitor_in", self.agent_parser))

		# COMMAND
	
		re_command_burst = [
			re_time + " " + re_entry_type_notify + " " +
			re_bold + r"(?P<command_burst_type>)" + re_nobold +
			" has applied bonuses to " +
			re_bold + r"(?P<boosted_ships_count>\d+)" + re_nobold +
			" fleet members."
		]
		self.matching_rules.append(MedusaParser.MatchingRule(re_command_burst, "command", "command_burst", self.agent_parser))
	
		# OTHERS
	
		re_timestamped_other = re_time
		self.matching_rules.append(("other", "message", re.compile(re_timestamped_other)))
	
	
	def build_matched_log_entry(self, rule, match_result, log_str) :
		data = match_result.groupdict()
		data["log_str"] = log_str
		data["session_owner"] = self.session_owner #! TODO
		if rule.rule_name.endswith("_in") : data["target_pilot"] = self.session_owner
		elif rule.rule_name.endswith("_out") : data["src_pilot"] = self.session_owner
		elif "src_you" in data and data["src_pilot"] == None : data["src_pilot"] = self.session_owner
		elif "target_you" in data and data["target_pilot"] == None : data["target_pilot"] = self.session_owner
		for k in data.keys() :
			if data[k] is not None :
				data[k] = data[k].strip()
		return {rule.category : {rule.rule_name : [data]}}
	
	def parse(self, log_entry_str) :
		if log_entry_str == None : return {}
		for rule in self.matching_rules :
			m = rule.match(log_entry_str)
			if m is not None :
				r = self.build_matched_log_entry(rule, m, log_entry_str)
				if self.debug :
					print("matched rule " + rule.rule_name + " : ")
					pprint.pprint(r)
				return r
		return {}

	def __init__(self, session_owner, agent_parser = None, debug = False) :
		self.debug = debug
		self.session_owner = session_owner
		if agent_parser : # if agent parser is supplied
			self.agent_parser = agent_parser
		else : # late default initialization
			self.agent_parser = AgentParser(debug = debug)
		self.init_rules()

if __name__ == "__main__" :
	
	testre = r"(?P<target_corp_ticker>\[((\w|-)+ ?)+\])?\((?P<target_ship_type>((\w|-)+ ?)+)\)</b><font size=\d+><color=0x[0-9a-fA-F]{8}>((<font size=\d+><color=0x[0-9a-fA-F]{8}>)|(<color=0x[0-9a-fA-F]{8}><font size=\d+>)) - (?P<weapon>(\w+(-\w+)? ?)+)( - (?P<hit_type>((\w|-)+ ?)+))?(</font>)?"
	teststr = "[2MHS](Fortizar)</b><font size=10><color=0x77ffffff> - Garde II - Penetrates"

	m = re.match(testre, teststr)
	if m is None : 
		print("test match failed")
	else :
		print("test match success")
		pprint.pprint(m.groupdict())
	exit()

	parser = MedusaParser("Dummy McDum", debug = True)
	test_logs_filename = "20200711_094402.txt"
	with open(test_logs_filename, "r", encoding='utf8') as f :
		for l in f.readlines() :
			print("  --  new line  --\n" + l)
			entry_collection = parser.parse(l)
			pprint.pprint(entry_collection)
			print("\n")