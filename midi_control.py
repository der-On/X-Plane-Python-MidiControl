import sched, time, sys
from pygame import midi
from BaseHTTPServer import HTTPServer,BaseHTTPRequestHandler

# the default midi in devices if none were specified
DEFAULT_DEVICES = [3]

SLEEP_TIME = 0.01 # time interval between midi polls in seconds
SLEEP_TIME_MS = SLEEP_TIME*1000 # time interval between midi polls in miliseconds

# midi states
NOTE_ON = 144
NOTE_OFF = 128
CC = 176
PROG_CHANGE = 192

# init pyGame's midi module
midi.init()

# array of active midi inputs
global midiIns
midiIns = []

# define server
global httpd
httpd = None

class server(HTTPServer):
    allow_reuse_address = True

class request(BaseHTTPRequestHandler):
	def do_GET(self):	
		self.send_response(200)
		self.send_header('Content-type', 'text/json')
		self.end_headers()
		self.wfile.write(str(get_all_signals()))
		return
	

#class RequestHandler(SimpleXMLRPCRequestHandler):
#	pass


def run(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):
	global httpd
	server_address = ('', 8000)
	httpd = server_class(server_address, handler_class)
	httpd.serve_forever()


def stop():
	global httpd
	httpd.socket.close()
	print("\nServer stopped")


def list_devices():
	for i in range(0,midi.get_count()):
		info = midi.get_device_info(i)
		if (info[2] == 1):
			print('%d: %s' % (i,info[1]))


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

def start(devices):
	init_devices(devices)
	
	run(server_class=server,handler_class=request)

def test_mode(devices):
	init_devices(devices)

	s = sched.scheduler(time.time, time.sleep)
	
	def main_loop(sc):
		get_all_signals(True)
	
		# call again
		sc.enter(SLEEP_TIME, 1, main_loop,(sc,))

	# start main loop
	s.enter(SLEEP_TIME,1,main_loop,(s,))
	s.run()


def parse_args():
	if '-l' in sys.argv or '-d' in sys.argv or '-t' in sys.argv:
		testMode = False

		if '-t' in sys.argv: testMode = True	

		if '-l' in sys.argv:
			list_devices()
	
		if '-d' in sys.argv:
			i = sys.argv.index('-d')
			if len(sys.argv)>i+1:
				# get devices list
				devices_t = sys.argv[i+1].split(',')
				devices = []
				for i in range(0,len(devices_t)):
					device = int(devices_t[i])
					# if device exists add it to list
					if device_exists(device):
						devices.append(device)
						print("Using midi device: %s" % (midi.get_device_info(device)[1]))
					else: print("Seems like the device #%d does not exist. Is it plugged in?" % device)

				if testMode:
					print("Running in test mode. No server was opened and your midi signals will be printed.")
					test_mode(devices)
				else: start(devices)
			else:
				print("Please specify the number of midi-in device(s)")

	else:
		print("Command line arguments:\n-l			Print out a list of midi-devices\n-d [device numbers]	Comma seperated list of device numbers to use. E.g. '2,3' (no spaces!)\-t			Run in test mode")
		

# if script was called from command line parse the arguments
if len(sys.argv)>0:
	parse_args()
else:
	start(DEFAULT_DEVICES)
