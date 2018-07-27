#!/usr/bin/python3
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=PendingDeprecationWarning)
    import revpimodio2
from time import sleep, time
import urllib.request 
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO
from ZODB import FileStorage, DB
import transaction
import json
import logging, sys
from pprint import pprint
import signal
from copy import deepcopy
from multiprocessing import Process, Queue
import os
from queue import Empty

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

def reassign(ordbok):
    temp = {}
    temp = ordbok
    return temp

def cyclewait():
    sleep(0.2)

class ventmotor:
    def __init__(self, go_up, go_down, up_switch, down_switch, io, db2, motor_name):
        self.databas = db2
        self.go_up = go_up
        self.go_down = go_down
        self.up_switch = up_switch
        self.down_switch = down_switch
        self.motor_name = motor_name
        self.io = io
        self.rangemargin = 1
        self.mem_go_up = True
        self.mem_go_down = True
        global queue

    def reinit(self):
        self.io.setoutput(self.go_down, True) 
        self.io.setoutput(self.go_up, False)  
        cyclewait()      
        while self.io.getoutput(self.down_switch) == True:
            sleep(0.5)
            logging.debug('Ventmotor: reinit, go down')

        self.io.setoutput(self.go_down, False) 
        self.io.setoutput(self.go_up, False)

        self.databas['data'][self.motor_name]['confirm'] = 'confirm'
        self.databas['data'] = reassign(self.databas['data'])
        transaction.commit()

        while self.databas['data'][self.motor_name]['confirm'] == 'confirm':
            sleep(1)
            logging.debug('Waiting for user input')

    def cleanstate(self):
        if self.databas['data'][self.motor_name]['cleanstate'] is True:
            logging.debug('Motor is in clean state')
            return True
        else:
            logging.debug('Motor is not in clean state')
            self.reinit() 
            self.databas['data'][self.motor_name]['cleanstate'] = True
            self.databas['data'] = reassign(self.databas['data'])
            transaction.commit()
            return False

    def verifyposition(self, position):
        if position > self.databas['data'][self.motor_name]['ranger']:
            logging.debug('Position higher than range')
            return False

        if position < 0:
            logging.debug('Position lower than range')
            return False

        logging.debug('Position in range')
        return True

    def phasesequence(self):
        if self.io.phasesequence() is True:
            logging.warning('Phasesequence fail')
            return False
        return True

    def moveabsoluteposition(self, position):
        
        if self.cleanstate() is False:
            return False

        if self.verifyposition(position) is False:
            return False

        if self.databas['data'][self.motor_name]['confirm'] == 'confirm':
            logging.debug('Motor halt')
            return False

        if self.databas['data'][self.motor_name]['confirm'] == 'confirmed':
            logging.debug('Window down confirmed, resetting.')
            self.databas['data'][self.motor_name]['position'] = 0
            self.databas['data'][self.motor_name]['confirm'] = 'no'
            self.databas['data'] = reassign(self.databas['data'])
            transaction.commit()

        self.originposition = self.databas['data'][self.motor_name]['position']
        movement = abs(position - self.originposition)
        
        if movement < 2 or position == 0:
        	logging.debug('Movement to little')
        	return False

        queue.put([time(), True])
        self.databas['data'][self.motor_name]['cleanstate'] = False
        self.databas['data'] = reassign(self.databas['data'])
        transaction.commit()

        if position > self.originposition:
            go_up = True

            if self.mem_go_up is False:
                logging.debug('Upgoing moment switch fail')
                return False
                
            logging.debug('Set output %s True for %s seconds', self.go_up, movement)
            self.io.setoutput(self.go_up, True)

        elif position <= self.originposition:
            go_up = False

            logging.debug('Set output %s True for %s seconds', self.go_down, movement)
            self.io.setoutput(self.go_down, True)

        
        endtime = time() + movement
        now = time()

        sleep(0.1)

        while True:
            sleep (0.05)
            #logging.debug('Sleeping 0.05')
            queue.put([time(), True])
                  
            if endtime < time():
                if position is not 0 or go_up is True:
                    logging.debug('Finished running motor')
                    break

            if self.phasesequence() is False:
                break

            if self.io.getoutput(self.up_switch) is False and go_up is True:
                self.mem_go_up = False
                self.mem_go_down = True
                logging.info('Up moment switch fail')
                break

            if self.io.getoutput(self.down_switch) is False and go_up is False:
                if 5 > self.originposition - (time() - now):
                    logging.info('Down Moment switch on at position %s, resetting', self.originposition - (time() - now))
                    self.databas['data'][self.motor_name]['position'] = 0
                else:
                    logging.info('Down Moment switch on at position %s, halt', self.originposition - (time() - now))
                    self.databas['data'][self.motor_name]['confirm'] = 'confirm'
                    
                self.databas['data'] = reassign(self.databas['data'])
                transaction.commit()
                break

        if go_up is True:
            logging.debug('Set output %s False', self.go_up)
            self.io.setoutput(self.go_up, False)
            new_position = self.originposition + (time() - now) + self.databas['data'][self.motor_name]['uplag']
            
        elif go_up is False:
            logging.debug('Set output %s False', self.go_down)
            self.io.setoutput(self.go_down, False)
            if self.databas['data'][self.motor_name]['position'] is not 0:
                new_position = self.originposition - (time() - now) - self.databas['data'][self.motor_name]['downlag']
            else:
                new_position = 0

        queue.put([time(), False])

        self.databas['data'][self.motor_name]['cleanstate'] = True
        self.databas['data'][self.motor_name]['position'] = new_position
        self.databas['data'] = reassign(self.databas['data'])
        transaction.commit()


    def moverelativeposition(self, position, direction):
        if direction == 'none':
            return
        if direction == 'up':
            new_position = self.databas['data'][self.motor_name]['position'] + position
        else:
            new_position = self.databas['data'][self.motor_name]['position'] - position
            
        if new_position > self.databas['data'][self.motor_name]['ranger']:
            new_position = self.databas['data'][self.motor_name]['ranger']
        if new_position < 0:
            new_position = 0

        logging.info('Motor %s Ändrar till läge %s', self.motor_name, new_position)
        self.moveabsoluteposition(new_position)


class io():
    def __init__(self):
        self.revpi = revpimodio2.RevPiModIO(autorefresh=False)

    def setoutput(self, output, value):
        if output == 'O_1':
            self.revpi.io.O_1.value = value
        elif output == 'O_2':
            self.revpi.io.O_2.value = value
        elif output == 'O_3':
            self.revpi.io.O_3.value = value
        elif output == 'O_4':
            self.revpi.io.O_4.value = value
        elif output == 'W1':
            self.revpi.io.O_11.value = value
        elif output == 'W2':
            self.revpi.io.O_12.value = value
        elif output == 'H':
            self.revpi.io.O_13.value = value
        elif output == 'L':
            self.revpi.io.O_14.value = value
        else:
            return
            
        if value == True:
            if output == 'O_1' or output == 'O_2':
                self.revpi.core.A1 = revpimodio2.RED
            elif output == 'O_3' or output == 'O_4':
                self.revpi.core.A2 = revpimodio2.RED
        else:
            if output == 'O_1' or output == 'O_2':
                self.revpi.core.A1 = revpimodio2.GREEN
            elif output == 'O_3' or output == 'O_4':
                self.revpi.core.A2 = revpimodio2.GREEN

        self.revpi.writeprocimg()


    def getoutput(self, output):
        self.revpi.readprocimg()
        if output == 'I_1':
            return self.revpi.io.I_1.value
        elif output == 'I_2':
            return self.revpi.io.I_2.value
        elif output == 'I_3':
            return self.revpi.io.I_3.value
        elif output == 'I_4':
            return self.revpi.io.I_4.value
        elif output == 'O_1':
            return self.revpi.io.O_1.value
        elif output == 'O_3':
            return self.revpi.io.O_3.value
        elif output == 'deg':
            return int(self.revpi.io.Input_Word_2.value / 10)
        elif output == 'lux':
            return self.revpi.io.Input_Word_1.value / 10
        elif output == 'hum':
            return int(self.revpi.io.Input_Word_3.value / 10)


    def phasesequence(self):
        #True means phase sequence and loss monitoring ok.
        self.revpi.readprocimg()
        return self.revpi.io.I_9.value


class tempregulator():
    def __init__(self, factor=4):
        self.setpoint = 1
        self.correction = 0
        self.direction = 'none'
        self.factor = factor

    def update(self, temp, setpoint):
        self.correction = abs(temp - int(setpoint)) * self.factor
        if temp - 1 > int(setpoint):
            self.direction = 'up'
        elif temp + 1 < int(setpoint):
            self.direction = 'down'
        else:
            self.direction = 'none'
            self.correction = 0

class weatherserver(threading.Thread):
    def __init__(self, db1):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db1 = db1
        
    def run(self):
        while True:
            with urllib.request.urlopen("https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/13.528156/lat/59.921701/data.json") as url:
                data = json.loads(url.read().decode())
                self.db1['data']['weather']['timestamp'] = data['timeSeries'][0]['validTime']

                for value in data['timeSeries'][0]['parameters']:
                    if value['name'] == 't':
                        self.db1['data']['weather']['temperature'] = value['values'][0]
                    if value['name'] == 'gust':
                        self.db1['data']['weather']['windspeed'] = value['values'][0]
                    if value['name'] == 'wd':
                        self.db1['data']['weather']['winddirection'] = value['values'][0]
                    if value['name'] == 'r':
                        self.db1['data']['weather']['humudity'] = value['values'][0]
                    if value['name'] == 'tcc_mean':
                        self.db1['data']['weather']['cloudness'] = value['values'][0]

                self.db1['data'] = reassign(self.db1['data'])
                transaction.commit()
            sleep(1000)

class sensorsync(threading.Thread):
    def __init__(self, db1, io):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db1 = db1
        self.io = io
        
    def run(self):
        while True:
                logging.debug('Sensorsync: sync')
                self.db1['data']['lux'] = self.io.getoutput('lux')
                self.db1['data']['hum'] = self.io.getoutput('hum')
                self.db1['data']['deg'] = self.io.getoutput('deg')
                self.db1['data'] = reassign(self.db1['data'])
                transaction.commit()
                sleep(30)

class webserver(threading.Thread):
    def __init__(self, db1, db2):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db1 = db1
        self.db2 = db2
        app = Flask(__name__, static_url_path='/static')
        app.config['SECRET_KEY'] = 'secret!'
        socketio = SocketIO(app)
        self.socketio = socketio

        @app.route("/")
        def index():
            return render_template('index.html')

        @socketio.on('data_send', namespace='/test')
        def handle_client_connect_event(json):
            logging.debug('Webserver: Sparar JSON data: %s', json)
            for key in json:
                if type(json[key]) is dict:
                    for key2 in json[key]:
                        self.db1['data'][key][key2] = json[key][key2]
                else:
                    self.db1['data'][key] = json[key]
            self.db1['data'] = reassign(self.db1['data'])
            transaction.commit()

        @socketio.on('connected', namespace='/test')
        def ccl(json):
            self.socketio.emit('my_response', self.db1['data'], namespace='/test')
            logging.debug('Webserver: Ny anvandare ansluten: %s', json)

        @app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory('static', path)

        self.thread = socketio.start_background_task(target=self.push_updates_thread)


        socketio.run(app, host='0.0.0.0', port=5000)


    def push_updates_thread(self):
        self.db1_comp2 = {}
        self.db1_comp2['data'] = deepcopy(self.db2['data'])
    
        while True:
            self.socketio.sleep(1)
            if self.db1_comp2['data'] != self.db2['data']:
                logging.debug('Webserver: skickar ny data till webbläsare')
                self.socketio.emit('my_response', self.db2['data'], namespace='/test')

                self.db1_comp2['data'] = deepcopy(self.db2['data'])
                


class database():
    def __init__(self):
        storage = FileStorage.FileStorage('database.fs')
        db = DB(storage)
        self.connection = db.open()
        
    def newconn(self):
        return self.connection.root()

class ventilationserver(threading.Thread):
    def __init__(self, db2):
        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()
        self.db2 = db2
        self.io = io()

    def run(self):
        motorsyd = ventmotor('O_3', 'O_4', 'I_3', 'I_4', self.io, self.db2, 'motorsyd')
        motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', self.io, self.db2, 'motornord')
        regulator = tempregulator()
     
        while not self.shutdown_flag.is_set():            

            if self.db2['data']['VentAutSwitch'] is True:
                time_u = time()
                while self.db2['data']['VentAutSwitch'] is True:
                    if time_u + 1 < time():    
                        regulator.update(self.io.getoutput('deg'), self.db2['data']['TempSetPointDay'])
                        motornord.moverelativeposition(regulator.correction, regulator.direction)
                        motorsyd.moverelativeposition(regulator.correction, regulator.direction)
                        logging.debug('Ventilatonserver: korrigering %s riktning %s', regulator.correction, regulator.direction)
                        time_u = time()
                    logging.debug('Ventilatonserver: Automatiskt läge')
                    sleep(1)
            else:
                motornordposition = int(self.db2['data']['motornord']['movetoposition']) / 100 * self.db2['data']['motornord']['ranger']
                motornord.moveabsoluteposition(int(motornordposition))
                motorsydposition = int(self.db2['data']['motorsyd']['movetoposition']) / 100 * self.db2['data']['motorsyd']['ranger']
                motorsyd.moveabsoluteposition(int(motorsydposition))
                logging.debug('Ventilatonserver: Manuellt läge')
                sleep(1)

            if int(self.db2['data']['TempSetPointHeater']) < self.db2['data']['deg']:
                print('Setting heater on')
                self.io.setoutput('H', True)
            elif int(self.db2['data']['TempSetPointHeater']) + 1 > self.db2['data']['deg']:
                print('Setting heater off')
                self.io.setoutput('H', False)              

        
        print('Setting output to default values')
        modio = revpimodio2.RevPiModIO(autorefresh=False)
        modio.setdefaultvalues()
        modio.writeprocimg()
        
        logging.info('Ventilatonserver: Avslutad')


def createdatabas(db):
    db['data'] = {  'TempSetPointDay': 22,
                    'TempSetPointHeater': 10,
                    'VentAutSwitch':   False,
                    'deg' : 0,
                    'hum': 0,
                    'lux': 0,
                    
                    'motorsyd': {    'position': 0,
                    				 'downlag': 0.36,
                    				 'uplag': 0.14, 
                                     'movetoposition': 0,
                                     'halt': False,
                                     'confirm': 'no',
                                     'upcount': 0,
                                     'downcount': 0,
                                     'cleanstate': True,
                                     'ranger': 160},

                    'motornord': {   'position': 0, 
                    				 'downlag': 0.60,
                    				 'uplag': 0.16, 
                                     'movetoposition': 0,
                                     'halt': False,
                                     'confirm': 'no',
                                     'upcount': 0,
                                     'downcount': 0,
                                     'cleanstate': True,
                                     'ranger': 160},

                    'weather':  {    'timestamp': 0,
                                     'temperature': 0,
                                     'windspeed': 0,
                                     'cloudness': 0,
                                     'humudity': 0,
                                     'winddirection': 0}
              }
    transaction.commit()

def signal_handler(signum, frame):
    print('Caught signal %d' % signum)
    raise serviceexit

class serviceexit(Exception):
    pass

def runner(queue):
    os.nice(5)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    global ventilationserver
    global weatherserver
    global sensorsync
    global webserver

    try:
        root = database()
    
        ###updatencomment to create databas###
        #db = root.newconn()
        #createdatabas(db)

        ventilationserver   = ventilationserver(root.newconn())        
        ventilationserver.start()

        weatherserver       = weatherserver(root.newconn())
        weatherserver.start()

        sensorsync       = sensorsync(root.newconn(), io())
        sensorsync.start()

        webserver           = webserver(root.newconn(), root.newconn())
        webserver.start()

        while True:
            sleep(1)

    except serviceexit:
        ventilationserver.shutdown_flag.set()
        ventilationserver.join()


if __name__ == "__main__":
	queue = Queue()
	runner = Process(target=runner, args=((queue),))
	runner.start()
	item = [0.0, False]

	try:
		while True:
			try:
				item = queue.get(timeout=1)
				#logging.debug("Vakthund: Ingen körning meddelad")
	            
			except Exception as error:
				#logging.debug("Vakthund: Timeout {}".format(str(error)))
				pass
	        
			if item[1] is True and item[0] + 3 < time():
				print('Vakthund: Mer än 3 sekunder sen')
				runner.terminate()
				modio = revpimodio2.RevPiModIO(autorefresh=False)
				modio.setdefaultvalues()
				modio.writeprocimg()
				while True:
					sleep(1)
					logging.debug('Process avslutad')
			else:
				#print('Vakthund: I tid eller körning pågår ej')
				pass
			sleep(0.04)

	except serviceexit:
		logging.info('Waiting for love')
		runner.join()
		logging.info('Love is here')

