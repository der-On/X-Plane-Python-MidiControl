import os.path
import urllib, os
from ConfigParser import ConfigParser
from XPLMPlugin import *
from XPLMProcessing import *
from XPLMDataAccess import *
from XPLMDefs import *
from XPLMMenus import *
from XPLMDisplay import *
from XPLMGraphics import *
from XPLMPlanes import *
from XPWidgetDefs import *
from XPWidgets import *
from XPStandardWidgets import *

try:
	from pygame import midi
	WITH_PYGAME = True
except:
	WITH_PYGAME = False

SCRIPTS_PATH = os.path.join(os.getcwd(),"Resources","plugins","PythonScripts")

SLEEP_TIME = 0.1

# XPlane Dataref Datatypes
INT_TYPE = 1
FLOAT_TYPE = 2
DOUBLE_TYPE = 4
FLOATARRAY_TYPE = 8
INTARRAY_TYPE = 16

# the default midi in devices if none were specified
DEFAULT_DEVICES = [3]

# midi states
NOTE_ON = 144
NOTE_OFF = 128
CC = 176
PROG_CHANGE = 192

# init pyGame's midi module
if WITH_PYGAME:
	try:
		midi.init()
	except:
		WITH_PYGAME = False

# array of active midi inputs
global midiIns
midiIns = []

def get_all_signals(verbose = False):
	global midiIns
	signals = []
	for midiIn in midiIns:
		signals.extend(get_signals(midiIn,verbose))

	return signals

def get_signals(midiIn,verbose = False):
	signals = []
	if midiIn.poll():
		# print out midi signals
		buf = midiIn.read(100)

		t = buf[-1][1] - (SLEEP_TIME_MS)

		for signal in buf:
			if signal[1] >= t: # only return latest signals
				if signal[0][0] == NOTE_ON:
					signals.append(("NOTE_ON",signal[0][1],signal[0][2]))
				elif signal[0][0] == NOTE_OFF:
					signals.append(("NOTE_OFF",signal[0][1],signal[0][2]))
				elif signal[0][0] == CC:
					signals.append(("CC",signal[0][1],signal[0][2]))
				elif signal[0][0] == PROG_CHANGE:
					signals.append(("PROG_CHANGE",signal[0][1],signal[0][2]))

				if len(signals) and verbose:
					print("%s n:%d value:%d" % (signals[-1][0],signals[-1][1],signals[-1][2]))
	return signals


def device_exists(device):
	if midi.get_count()-1>=device:
		return True
	else:
		return False


def init_devices(devices):
	global midiIns
	midiIns = []
	for device in devices:
		midiIns.append(midi.Input(device))

def uninit_devices():
	global midiIns
	for midiIn in midiIns:
		midiIn.close()

def translate(value, leftMin, leftMax, rightMin, rightMax):
	# Figure out how 'wide' each range is
	leftSpan = leftMax - leftMin
	rightSpan = rightMax - rightMin

	# Convert the left range into a 0-1 range (float)
	valueScaled = float(value - leftMin) / float(leftSpan)

	# Convert the 0-1 range into a value in the right range.
	return rightMin + (valueScaled * rightSpan)


def within(v,vFrom,vTo):
	vMin  = min(vFrom,vTo)
	vMax = max(vFrom,vTo)
	return v>=vMin and v<=vMax

def getDataref(dataref,index = 0):
	dref = XPLMFindDataRef(dataref)
	if type(dref).__name__=='int':
		drefType = XPLMGetDataRefTypes(dref)
		if drefType and drefType!=0:
			if XPLMCanWriteDataRef(dref) and drefType in (INT_TYPE,FLOAT_TYPE,DOUBLE_TYPE,INTARRAY_TYPE,FLOATARRAY_TYPE):
				if drefType == INT_TYPE:
					return XPLMGetDatai(dref)
				elif drefType == FLOAT_TYPE:
					return XPLMGetDataf(dref)
				elif drefType == DOUBLE_TYPE:
					return XPLMGetDatad(dref)
				elif drefType == INTARRAY_TYPE:
					va = []
					XPLMGetDatavi(dref,va,index,1)
					return va[0]
				elif drefType == FLOATARRAY_TYPE:
					va = []
					XPLMGetDatavf(dref,va,index,1)
					return va[0]
	return None

def setDataref(dataref,value,index = 0,length = 1):
	dref = XPLMFindDataRef(dataref)
	if type(dref).__name__=='int':
		drefType = XPLMGetDataRefTypes(dref)
		if drefType and drefType!=0:
			if XPLMCanWriteDataRef(dref) and drefType in (INT_TYPE,FLOAT_TYPE,DOUBLE_TYPE,INTARRAY_TYPE,FLOATARRAY_TYPE):
				if drefType == INT_TYPE:
					return XPLMGetDatai(dref)
				elif drefType == FLOAT_TYPE:
					return XPLMGetDataf(dref)
				elif drefType == DOUBLE_TYPE:
					return XPLMGetDatad(dref)
				elif drefType == INTARRAY_TYPE:
					va = []
					for i in range(0,length): va.append(int(value))
					return XPLMSetDatavi(dref,va,index,length)
				elif drefType == FLOATARRAY_TYPE:
					va = []
					for i in range(0,length): va.append(float(value))
					return XPLMSetDatavf(dref,va,index,length)
	return None

class PythonInterface:
	def XPluginStart(self):
		self.Name = "MidiControl"
		self.Sig = "OndrejBrinkel.Python.MidiControl"
		self.Desc = "Control Datarefs with midi device"

		# create menu
		self.SubMenuItem = XPLMAppendMenuItem(XPLMFindPluginsMenu(), "Midi Control", 0, 1)
		self.MenuHandlerCB = self.MenuHandlerCallback
		self.Menu = XPLMCreateMenu(self, "Midi Control", XPLMFindPluginsMenu(), self.SubMenuItem, self.MenuHandlerCB,	0)
		XPLMAppendMenuItem(self.Menu, "Reload configuration", 0, 1)
		XPLMAppendMenuItem(self.Menu, "Toggle midi input monitoring", 1, 1)

		# midi input window
		self.MidiInWidget = None
		#self.MidiInWidgetCB = self.MidiInWidget

		# midi devices Window
		self.devices = []

		return self.Name, self.Sig, self.Desc

	def Uninit(self):
		if self.MidiInWidget:
			XPDestroyWidget(self,self.MidiInWidget,1)
			self.MidiInWidget = None

		if self.Menu:
			XPLMDestroyMenu(self,self.Menu)
			self.Menu = None

	def XPluginStop(self):	
		self.Uninit()
		pass
	
	def XPluginEnable(self):
		self.midiInBuffer = ''
		if WITH_PYGAME:
			if len(self.devices)==0:
				init_devices(DEFAULT_DEVICES)
			else:
				init_devices(self.devices)
			
		self.FlightLoopCB = self.Update
		XPLMRegisterFlightLoopCallback(self,self.FlightLoopCB,1.0,0)
		self.ReloadInis()
		return 1

	def MenuHandlerCallback(self, inMenuRef, inItemRef):
		if inItemRef==0:
			self.ReloadInis()
		elif inItemRef==1:
			if self.MidiInWidget:				
				if(XPIsWidgetVisible(self.MidiInWidget)):
					XPHideWidget(self.MidiInWidget)
				else:
					XPShowWidget(self.MidiInWidget)
				pass
			else:
				self.CreateMidiInWidget(50, 600, 200, 100)
				if(not XPIsWidgetVisible(self.MidiInWidget)):
					XPShowWidget(self.MidiInWidget)
		pass

	def CreateMidiInWidget(self,x,y,w,h):
		x2 = x+w
		y2 = y-h

		# Create the Main Widget window
		self.MidiInWidget = XPCreateWidget(x, y, x2, y2, 1, 'Midi Control - last input:', 1,	0, xpWidgetClass_MainWindow)

		# Add Close Box decorations to the Main Widget
		XPSetWidgetProperty(self.MidiInWidget, xpProperty_MainWindowHasCloseBoxes, 1)

		# Create the Sub Widget1 window
#		MidiInWindow = XPCreateWidget(x+10, y-20, x2-10, y2+10,
#					     1,		# Visible
#					     "",		# desc
#					     0,		# root
#					     self.MidiInWidget,
#					     xpWidgetClass_SubWindow)

		# Set the style to sub window
#		XPSetWidgetProperty(MidiInWindow, xpProperty_SubWindowType, xpSubWindowStyle_SubWindow)

		# Assignments text
		self.MidiInWidgetCaption = XPCreateWidget(x+20, y-30, x2-20, y2+20,1, self.midiInBuffer, 0, self.MidiInWidget,xpWidgetClass_Caption)

		# Register our widget handler
		self.MidiInHandlerCB = self.MidiInHandler
		XPAddWidgetCallback(self, self.MidiInWidget, self.MidiInHandlerCB)

	def MidiInHandler(self, inMessage, inWidget,    inParam1, inParam2):
		if (inMessage == xpMessage_CloseButtonPushed):
			XPHideWidget(self.MidiInWidget)
			return 1
		return 0

	def ReloadInis(self):
		self.LoadPresets(os.path.join(SCRIPTS_PATH,'midi_control_presets.ini'))
		self.LoadMidiBindings(os.path.join(SCRIPTS_PATH,'midi_control.ini'))
		plane_path = XPLMGetNthAircraftModel(0)
		plane_path = os.path.dirname(plane_path[1])

		presets_file = os.path.join(plane_path,'midi_control_presets.ini')
		bindings_file = os.path.join(plane_path,'midi_control.ini')

		if os.path.exists(presets_file) and os.path.isfile(presets_file):
			self.LoadPresets(presets_file,True)
		if os.path.exists(bindings_file) and os.path.isfile(bindings_file):
			self.LoadMidiBindings(bindings_file,True)

	def XPluginDisable(self):
		if WITH_PYGAME: uninit_devices()
		XPLMUnregisterFlightLoopCallback(self,self.FlightLoopCB,0)
		pass

	def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
		if inMessage == XPLM_MSG_PLANE_LOADED and inParam == 0: # user plane loaded, so load midi bindings of the plane on top of base bindings
			# self.LoadMidiBindings(SCRIPTS_PATH+'midi_control.ini')
			pass
	
	def UpdateDatarefs(self,signals):
		for signal in signals:
			signalType = signal[0]
			n = str(signal[1])
			
			if signalType in self.bindings and n in self.bindings[signalType]:
				for binding in self.bindings[signalType][n]:
					self.UpdateDataref(signal,binding)

	def UpdateDataref(self,signal,binding):
		# check if the signal type and value is in bindings
		signalType = signal[0]
		n = str(signal[1])
		if len(signal)>2:
			v = signal[2]
		else:
			if signalType == 'NOTE_ON':
				v = 127
			elif signalType == 'NOTE_OFF':
				v = 0
			else:
				v = 0
		
		# ignore values out of midi range
		if within(v,binding['midi_range'][0],binding['midi_range'][1]):
			dref = binding['dataref']
			drefType = binding['dataref_type']
			drefValue_orig = self.GetDataref(dref,drefType,binding['dataref_index'][0],binding['dataref_index'][1])

			if type(drefValue_orig).__name__ == 'list':
				for i in range(0,len(drefValue_orig)):
					drefValue = self.GetUpdatedValue(v,dref,drefType,binding,drefValue_orig[i])
					self.SetDataref(dref,drefType,drefValue,binding['dataref_index'][0]+i,1)
					self.RunExecute(binding['post_execute'],drefValue_orig[i],drefValue)
			else:
				drefValue = self.GetUpdatedValue(v,dref,drefType,binding,drefValue_orig)
				self.SetDataref(dref,drefType,drefValue,binding['dataref_index'][0],binding['dataref_index'][1])
				self.RunExecute(binding['post_execute'],drefValue_orig,drefValue)

	def GetUpdatedValue(self,v,dref,drefType,binding,drefValue_orig):
			# determine value by linear mapping
			value = translate(v,float(binding['midi_range'][0]),float(binding['midi_range'][1]),binding['data_range'][0],binding['data_range'][1])

			if binding['steps']:
				step_size = float(binding['data_range'][1] - binding['data_range'][0])/float(binding['steps'])
				step = round((value-binding['data_range'][0])/step_size)
				value = float(binding['data_range'][0])+(step*step_size)
				
			if binding['toggle']:
				if drefValue_orig == binding['data_range'][0]:
					value = binding['data_range'][1]
				else:
					value = binding['data_range'][0]
			elif binding['relative']:
				value = self.RunAction(binding['pre_action'],drefValue_orig,value)
				self.RunExecute(binding['pre_execute'],drefValue_orig,value)
				value = drefValue_orig + value
			else:
				# get data range min and max
				data_min = min(binding['data_range'][0],binding['data_range'][1])
				data_max = max(binding['data_range'][0],binding['data_range'][1])

				# clip value to range
				if value<data_min:
					value = data_min
				elif value>data_max:
					value = data_max
					
				if binding['additive']:
					value_add = value - binding['last_value']
					value = self.RunAction(binding['pre_action'],drefValue_orig,value)
					self.RunExecute(binding['pre_execute'],drefValue_orig,value)
					binding['last_value'] = value
					value = drefValue_orig + value_add
				else:
					value = self.RunAction(binding['pre_action'],drefValue_orig,value)
					self.RunExecute(binding['pre_execute'],drefValue_orig,value)

			# run post action
			drefValue = self.RunAction(binding['post_action'],drefValue_orig,value)

			# clip to min and max
			if binding['data_min'] and drefValue<binding['data_min']: drefValue = binding['data_min']
			if binding['data_max'] and drefValue>binding['data_max']: drefValue = binding['data_max']

			# finally return the new value
			return drefValue

	def RunExecute(self,execute,data,value):
		if execute:
			exec execute

	def RunAction(self,action,data,value):
		if action:
			return eval(action)
		else: return value

	def GetDataref(self,dref,drefType,index = 0, length = 1):
		if drefType == INT_TYPE:
			return XPLMGetDatai(dref)
		elif drefType == FLOAT_TYPE:
			return XPLMGetDataf(dref)
		elif drefType == DOUBLE_TYPE:
			return XPLMGetDatad(dref)
		elif drefType == INTARRAY_TYPE:
			va = []
			XPLMGetDatavi(dref,va,index,length)
			return va
		elif drefType == FLOATARRAY_TYPE:
			va = []
			XPLMGetDatavf(dref,va,index,length)
			return va

	def SetDataref(self,dref,drefType,value,index = 0, length = 1):
		if drefType == INT_TYPE:
			return XPLMSetDatai(dref,int(value))
		elif drefType == FLOAT_TYPE:
			return XPLMSetDataf(dref,float(value))
		elif drefType == DOUBLE_TYPE:
			return XPLMSetDatad(dref,float(value))
		elif drefType == INTARRAY_TYPE:
			va = []
			for i in range(0,length): va.append(int(value))
			return XPLMSetDatavi(dref,va,index,length)
		elif drefType == FLOATARRAY_TYPE:
			va = []
			for i in range(0,length): va.append(float(value))
			return XPLMSetDatavf(dref,va,index,length)

	def Update(self,inFlightLoopCallback, inInterval,inRelativeToNow, inRefcon):
		if WITH_PYGAME: 
			signals = get_all_signals()
		else:
			signals = []
			try:
				sock = urllib.urlopen('http://localhost:8000')
				json = sock.read()
				sock.close()
				signals = eval(json)
			except:
				self.midiInBuffer="Midi control server not reachable."

		if signals and len(signals)>0:
			# update midi-in buffer
			self.midiInBuffer = ''
			for signal in signals:
				self.midiInBuffer+=str(signal)+'\n'
				
			self.UpdateDatarefs(signals)

		# update widget if any
		if self.MidiInWidget:
			XPSetWidgetDescriptor(self.MidiInWidgetCaption, self.midiInBuffer)
			
		return SLEEP_TIME
	
	def ApplyPreset(self,options):
		if 'preset' in options and options['preset'] in self.presets:
			for option in self.presets[options['preset']]:
				if option not in options:
					options[option] = self.presets[options['preset']][option]
	
		return options

	def LoadPresets(self,iniFile, overwrite = False):
		if overwrite == False:
			self.presets = {}
			
		cp = ConfigParser()
		cp.read(iniFile)
		for section in cp.sections():
			self.presets[section] = {}
			for option in cp.options(section):
				self.presets[section][option] = cp.get(section,option)
	
	def LoadMidiBindings(self,iniFile,overwrite = False):
		self.ini = {}
		if overwrite == False:
			self.bindings = {'CC':{},'NOTE_ON':{},'NOTE_OFF':{}}
		
		cp = ConfigParser()
		cp.read(iniFile)
		for section in cp.sections():
			# remove optional prefix from section
			parts = section.split('|',1)
			if len(parts)>1:
				dataref = parts[1]
			else: dataref = section
			
			if dataref not in self.ini:
				self.ini[dataref] = []
			options = {}
			
			for option in cp.options(section):
				options[option] = cp.get(section,option)
			self.ini[dataref].append(options)

		for dataref in self.ini:
			for options in self.ini[dataref]:
				options = self.ApplyPreset(options)
				if 'type' in options and 'n' in options:
					parts = dataref.split(' ',1)
					if len(parts)>1:
						dataref = parts[0]
						dataref_index = parts[1].split('/',1)
						dataref_index[0] = int(dataref_index[0])
						if len(dataref_index)<2:
							dataref_index.append(1)
						else: dataref_index[1] = int(dataref_index[1])
					else: dataref_index = [None,None]

					dref = XPLMFindDataRef(dataref)

					if type(dref).__name__=='int':
						drefType = XPLMGetDataRefTypes(dref)
						if drefType and drefType!=0:
							if XPLMCanWriteDataRef(dref) and drefType in (INT_TYPE,FLOAT_TYPE,DOUBLE_TYPE,INTARRAY_TYPE,FLOATARRAY_TYPE):
								binding = {'dataref':dref,'dataref_type':drefType,'dataref_index':dataref_index}

								# set ranges

								if 'midi_range' in options:
									binding['midi_range'] = eval(options['midi_range'])
								else:
									binding['midi_range'] = [0,127]

								if 'data_range' in options:
									binding['data_range'] = eval(options['data_range'])
								else: # TODO: automaticly find out the type of dataref and min, max values
									binding['data_range'] = [0.0,1.0]

								# is this an absolute or relative control? Defaults to absolute
								if 'relative' in options:
									binding['relative'] = options['relative']
								else: binding['relative'] = False

								# will changes of this control apply in an additive manner? Defaults to no
								if 'additive' in options:
									binding['last_value'] = 0.0
									binding['additive'] = options['additive']
								else: binding['additive'] = False

								# toggle action?
								if 'toggle' in options:
									binding['toggle'] = options['toggle']
								else: binding['toggle'] = False

								# value snapping
								if 'steps' in options:
									binding['steps'] = options['steps']
								else: binding['steps'] = None

								# data min, max
								if 'data_min' in options:
									binding['data_min'] = float(options['data_min'])
								else: binding['data_min'] = None
								if 'data_max' in options:
									binding['data_max'] = float(options['data_max'])
								else: binding['data_max'] = None

								if 'pre_action' in options:
									binding['pre_action'] = options['pre_action']
								else: binding['pre_action'] = None
								if 'post_action' in options:
									binding['post_action'] = options['post_action']
								else: binding['post_action'] = None

								if 'pre_execute' in options:
									binding['pre_execute'] = options['pre_execute']
								else: binding['pre_execute'] = None
								if 'post_execute' in options:
									binding['post_execute'] = options['post_execute']
								else: binding['post_execute'] = None

								# add binding to the list, create one if not already present
								if options['n'] not in self.bindings[options['type']]:
									self.bindings[options['type']][options['n']] = []
								self.bindings[options['type']][options['n']].append(binding)