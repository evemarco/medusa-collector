# Medusa status info generator function
# This file is a part of the Medusa project, a real-time combat logs analyzer for Eve Online
# Author : Tnemelc Abramovich

# generates a status_info dict from a logs_collection dict.
# A status_info dict is a simpler object in that it has inherently less entries than a logs_collection dict.
# As such, it is lighter and more suited for sharing, typically though the network and to a web server in charge of displaying the information.
# It aggregates informations in the provided log collection on a per-character basis, including incoming and outgoing dps, remote assistance, capacitor warfare, ewar...
# It is designed to be a convenient way to sum up key information for each active members and enemies appearing in the users games logs.
def make_status_info(logs_collection, dps_window, gametime) :
	# main status_info structure
	status_info = {}
	status_info["date"] = gametime.isoformat(timespec='seconds')
	status_info["characters"] = {}
	status_info["total"] = {
		'dps_in': 0,
		'dps_out': 0,
		'neut_in' : 0,
		'neut_out' : 0,
		'nos_in' : 0,
		'nos_out' : 0,
		'reps_in' : 0,
		'reps_out' : 0,
		'cap_transfer_in' : 0,
		'cap_transfer_out' : 0
	}
	
	def add_ship_type(status_info, pilot, ship_type) : 
		if ship_type is not None :
			status_info['characters'][pilot]["ship_type"] = ship_type

	# dps and alpha
	
	def add_damage(status_info, src_pilot, target_pilot, weapon_damage) :
		weapon_damage = int(weapon_damage)
		if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
		if not 'dps_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['dps_out'] = 0
		status_info['characters'][src_pilot]['dps_out'] += weapon_damage / dps_window
		if not 'alpha_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['alpha_out'] = 0
		status_info['characters'][src_pilot]['alpha_out'] = max(status_info['characters'][src_pilot]['alpha_out'], weapon_damage)
		
		if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
		if not 'dps_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['dps_in'] = 0
		status_info['characters'][target_pilot]['dps_in'] += weapon_damage / dps_window
		if not 'alpha_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['alpha_in'] = 0
		status_info['characters'][target_pilot]['alpha_in'] = max(status_info['characters'][target_pilot]['alpha_in'], weapon_damage)
	
	if 'dps' in logs_collection:
		# dps out
		if 'weapon_cycle_out' in logs_collection['dps'] :
			for e in logs_collection['dps']['weapon_cycle_out'] :
				add_damage(status_info, e["session_owner"], e["target_pilot"], e["weapon_damage"])
				add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				status_info['total']['dps_out'] += int(e['weapon_damage']) / dps_window
		
		# dps in
		if 'weapon_cycle_in' in logs_collection['dps'] : 
			for e in logs_collection['dps']['weapon_cycle_in'] :
				add_damage(status_info, e["src_pilot"], e["session_owner"], e["weapon_damage"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['dps_in'] += int(e['weapon_damage']) / dps_window
	
	def add_neut(status_info, src_pilot, target_pilot, neut_amount) :
		neut_amount = int(neut_amount)
		if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
		if not 'neut_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['neut_out'] = 0
		status_info['characters'][src_pilot]['neut_out'] += neut_amount / dps_window

		if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
		if not 'neut_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['neut_in'] = 0
		status_info['characters'][target_pilot]['neut_in'] += neut_amount / dps_window
	
	def add_nos(status_info, src_pilot, target_pilot, nos_amount) :
		nos_amount = int(nos_amount)
		if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
		if not 'nos_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['nos_out'] = 0
		status_info['characters'][src_pilot]['nos_out'] += nos_amount / dps_window

		if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
		if not 'nos_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['nos_in'] = 0
		status_info['characters'][target_pilot]['nos_in'] += nos_amount / dps_window

	if 'neut' in logs_collection:
		if 'neut_out' in logs_collection['neut'] :
			for e in logs_collection['neut']['neut_out'] :
				add_neut(status_info, e["session_owner"], e["target_pilot"], e["neut_amount"])
				add_ship_type(status_info, e["target_pilot"], e["target_ship_type"])
				status_info['total']['neut_out'] += int(e['neut_amount']) / dps_window
		if 'neut_in' in logs_collection['neut'] :
			for e in logs_collection['neut']['neut_in'] :
				add_neut(status_info, e["src_pilot"], e["session_owner"], e["neut_amount"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['neut_in'] += int(e['neut_amount']) / dps_window
		
		if 'nos_out' in logs_collection['neut'] :
			for e in logs_collection['neut']['nos_out'] :
				add_nos(status_info, e["session_owner"], e["target_pilot"], e["nos_amount"])
				add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				status_info['total']['nos_out'] += int(e['nos_amount']) / dps_window
		if 'nos_in' in logs_collection['neut'] :
			for e in logs_collection['neut']['nos_in'] :
				add_nos(status_info, e["src_pilot"], e["session_owner"], e["nos_amount"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['nos_in'] += int(e['nos_amount']) / dps_window
			
	
	# remote repair
	def add_remote_repair(status_info, src_pilot, target_pilot, repair_amount) :
		repair_amount = int(repair_amount)
		if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
		if not 'hps_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['hps_out'] = 0
		status_info['characters'][src_pilot]['hps_out'] += repair_amount / dps_window
		if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
		if not 'hps_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['hps_in'] = 0
		status_info['characters'][target_pilot]['hps_in'] += repair_amount / dps_window
	
	def add_remote_capacitor(status_info, src_pilot, target_pilot, energy_amount) :
		energy_amount = int(energy_amount)
		if not src_pilot in status_info['characters'] : status_info['characters'][src_pilot] = {}
		if not 'remote_capacitor_out' in status_info['characters'][src_pilot] : status_info['characters'][src_pilot]['remote_capacitor_out'] = 0
		status_info['characters'][src_pilot]['remote_capacitor_out'] += energy_amount / dps_window
		if not target_pilot in status_info['characters'] : status_info['characters'][target_pilot] = {}
		if not 'remote_capacitor_in' in status_info['characters'][target_pilot] : status_info['characters'][target_pilot]['remote_capacitor_in'] = 0
		status_info['characters'][target_pilot]['remote_capacitor_in'] += energy_amount / dps_window
	
	# remote repair out
	if 'remote_assist' in logs_collection : 
		if 'remote_shield_out' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_shield_out'] :
				add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_shield_amount"])
				add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				status_info['total']['reps_out'] += int(e['remote_shield_amount']) / dps_window
		if 'remote_shield_in' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_shield_in'] :
				add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_shield_amount"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['reps_in'] += int(e['remote_shield_amount']) / dps_window
		
		if 'remote_armor_out' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_armor_out'] :
				add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_armor_amount"])
				add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				status_info['total']['reps_out'] += int(e['remote_armor_amount']) / dps_window
		if 'remote_armor_in' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_armor_in'] :
				add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_armor_amount"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['reps_in'] += int(e['remote_armor_amount']) / dps_window
		
		if 'remote_hull_out' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_hull_out'] :
				add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_hull_amount"])
				add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				status_info['total']['reps_out'] += int(e['remote_hull_amount']) / dps_window
		if 'remote_hull_in' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_hull_in'] :
				add_remote_repair(status_info, e["src_pilot"], e["target_pilot"], e["remote_hull_amount"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['reps_in'] += int(e['remote_hull_amount']) / dps_window
		
		if 'remote_capacitor_out' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_capacitor_out'] :
				add_remote_capacitor(status_info, e["src_pilot"], e["target_pilot"], e["energy_amount"])
				add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				status_info['total']['cap_transfer_out'] += int(e['energy_amount'])
		if 'remote_capacitor_in' in logs_collection['remote_assist'] :
			for e in logs_collection['remote_assist']['remote_capacitor_in'] :
				add_remote_capacitor(status_info, e["src_pilot"], e["target_pilot"], e["energy_amount"])
				add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
				status_info['total']['cap_transfer_in'] += int(e['energy_amount']) / dps_window
		
	
	# remote repair in
	# ignored since already accounted through remote repair_out as long as all logis use the client

	# ewar
	if 'ewar' in logs_collection: 
		if 'scramble_attempt' in logs_collection['ewar']:
			for e in logs_collection['ewar']['scramble_attempt'] :
				if not e['target_pilot'] in status_info["characters"] : status_info['characters'][e['target_pilot']] = {}
				status_info['characters'][e['target_pilot']]["scrambled"] = True
				if "target_ship_type" in e : add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])

				if not e['src_pilot'] in status_info["characters"] : status_info['characters'][e['src_pilot']] = {}
				status_info['characters'][e['src_pilot']]["scrambling"] = True
				if "src_ship_type" in e : add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
		if 'disruption_attempt' in logs_collection['ewar']:
			for e in logs_collection['ewar']['disruption_attempt'] :
				if not e['target_pilot'] in status_info["characters"] : status_info['characters'][e['target_pilot']] = {}
				status_info['characters'][e['target_pilot']]["pointed"] = True
				if "target_ship_type" in e : add_ship_type(status_info, e["target_pilot"],e["target_ship_type"])
				if not e['src_pilot'] in status_info["characters"] : status_info['characters'][e['src_pilot']] = {}
				status_info['characters'][e['src_pilot']]["pointing"] = True
				if "src_ship_type" in e : add_ship_type(status_info, e["src_pilot"],e["src_ship_type"])
	
	return status_info
