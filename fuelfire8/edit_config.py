"""Read and modify FUELFIRE configuration files

example::
	
	>>> cf = ConfigFile(cfg_path)
	>>> cf.PresetModify([('risk', 'ONLY_H')], 'a new caption')
	
"""


class ConfigFile:
	"""FUELFIRE configuration file with methods to read, edit, and write
	parameters
	
	
	presets are defined which represent configurations of a few related
	parameters. The key define the groups of parameters and the presets
	define named sets of values (options) for a given key
	"""
	#parameter group headings used to index parameters in the fuelfire config file
	pheads = [
		'&GETBASIC', '&GETDEMO', '&GETAREA', '&GETWIND', '&GETFUEL', 
		'&GETSTRIKE', '&GETSTATES', '&GETLOW', '&GETMOD', '&GETHIGH', 
		'&GETVHIGH', '&GETEXTREME', '&GETSUPPRESS', '&GETOUTPUT', '&GETMOSAIC']
	
	#preset groups of parameters
	KEYS = {
		'fuel': [
			('&GETFUEL','IMMATURE_FUEL_FACTOR'),
			('&GETFUEL','MATURE_FUEL_FACTOR')],
		'risk': [
			('&GETSTATES','NO_FREQ'),
			('&GETSTATES','LO_FREQ'),
			('&GETSTATES','MOD_FREQ'),
			('&GETSTATES','HI_FREQ'),
			('&GETSTATES','VHI_FREQ'),
			('&GETSTATES','EX_FREQ')],
		'sup': [
			('&GETSUPPRESS','BEGIN_AT_STEP'),
			('&GETSUPPRESS','CANCEL_AT_STEP')],
		}
	
	#named preset combinations
	PRESETS = {
		'fuel': {
			'1-04'		:[1, 0.4],
			'1p5-04'	:[1.5, 0.4],
			'2-04'		:[2, 0.4],
			'2p5-04'	:[2.5, 0.4],
			'3-04'		:[3, 0.4],
			'4-04'		:[4, 0.4],
			'6-04'		:[6, 0.4],
			'8-04'		:[8, 0.4]},
		'risk': {
			'Def'		:[0,540,250,65,5,1],
			'ONLY_L'	:[0,100,0,0,0,0],
			'ONLY_M'	:[0,0,100,0,0,0],
			'ONLY_H'	:[0,0,0,100,0,0],
			'ONLY_E'	:[0,0,0,0,100,100]},
		'sup': {
			'SUP' 		:[0,9000],
			'NOSUP'		:[9000,9001]},
		}
	

	def __init__(self, configfile):
		"""Read config file and index parameter line numbers"""
		self.configfile = configfile
		self.LoadConfig()
		self.MapParams()	

	def PresetModify(self,presetlist,caption):
		"""Execute a list of modifications including a caption"""
		for (param,preset) in presetlist:
			self.PresetEdit(param,preset)
		self.ManualEdit('&GETBASIC','CAPTION',caption)
		self.WriteConfig()
	
	def PresetEdit(self,param,preset):
		"""Edit parameters for a given preset""" 
		keys = self.KEYS[param]
		vals = list(self.PRESETS[param][preset])
		for ((group,par),val) in zip(keys,vals):
			l = self.pmap.get(group).get(par)
			self.lines[l] = self.FormatLine(self.lines[l],val)

	def ManualEdit(self, group, par, val):
		"""Replace the value of the given group and parameter"""
		l = self.pmap.get(group).get(par)
		self.lines[l] = self.FormatLine(self.lines[l],val)

	def FormatLine(self, line, val):
		"""create formatted line containing new parameter"""
		return "{} {} \n".format(line[:line.find('=')+1], val)
		
	def LoadConfig(self):
		"""Read the configuration file"""
		with open(self.configfile, 'r') as f:
			self.lines = f.readlines()
			
	def WriteConfig(self):
		"""Write the modified config file"""
		with open(self.configfile, 'w') as f:
			[f.write(line) for line in self.lines]
			
	def MapParams(self):
		"""Creates a mapping of parameter heading and name to its configuration file line number"""
		self.pmap = dict([(phead,{}) for phead in self.pheads]) 
		p = 0
		isopen = False
		for (l,line) in enumerate(self.lines):
			line = line.strip()
			line = line.upper()
			if isopen == True:
				if line == '/': #signal to close
					isopen = False
					if p+1 < len(self.pheads):
						p = p+1 
				elif line.count('=') == 1:
					[key,val] = line.split('=')
					key = key.strip()
					self.pmap[self.pheads[p]][key] = l
			elif isopen == False:
				if line.count(self.pheads[p]) == 1:
					isopen = True
		


