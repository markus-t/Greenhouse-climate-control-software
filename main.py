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

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

def reassign(ordbok):
    temp = {}
    temp = ordbok
    return temp


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

    def testrange(self):
        self.io.setoutput(self.go_down, False)
        self.io.setoutput(self.go_up, True)
        sleep(0.5)
        while self.io.getoutput(self.up_switch) == True:
            sleep(0.5)
            logging.debug('Ventmotor: testrange: up while sleep 0.5 sec')

        logging.debug('Ventmotor: testrange: while up exit')

        self.io.setoutput(self.go_down, True) 
        self.io.setoutput(self.go_up, False)

        start_time = time()
        sleep(0.5)
        while self.io.getoutput(self.down_switch) == True:
            sleep(0.5)
            logging.debug('Ventmotor: testrange: down while sleep 0.5 sec')
        
        end_time = time() - self.rangemargin

        self.io.setoutput(self.go_down, False) 
        self.io.setoutput(self.go_up, False)

        self.databas['data'][self.motor_name]['ranger'] = int(end_time - start_time)
        self.databas['data'] = reassign(self.databas['data'])
        transaction.commit()

    def moveabsoluteposition(self, position):
        movement = position - self.databas['data'][self.motor_name]['position']
        if position > self.databas['data'][self.motor_name]['position']:
            logging.debug('Set output %s True for %s seconds', self.go_up, abs(movement))
            self.io.setoutput(self.go_up, True)
            now = int(time())
            endtime = int(time() + abs(movement))
            while endtime > now:
                sleep (0.1)
                logging.debug('Sleeping')
                now = int(time())
                #if self.io.phasesequence():
                #    return False

            self.io.setoutput(self.go_up, False)
            logging.debug('Set output %s False', self.go_up)

        elif position < self.databas['data'][self.motor_name]['position']:
            logging.debug('Set output %s True for %s seconds', self.go_down, abs(movement))
            self.io.setoutput(self.go_down, True)
            sleep(abs(movement))
            logging.debug('Set output %s False', self.go_down)
            self.io.setoutput(self.go_down, False)

        else: 
            return

        self.databas['data'][self.motor_name]['position'] = position
        self.databas['data'] = reassign(self.databas['data'])
        transaction.commit()

    def moverelativeposition(self, position, direction):
        if direction == 'up':
            new_position = position + self.databas['data'][self.motor_name]['position']
        else:
            new_position = position - self.databas['data'][self.motor_name]['position']

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
        else:
            return
            
        if value == True:
            self.revpi.core.A1 = revpimodio2.RED
        else:
            self.revpi.core.A1 = revpimodio2.GREEN

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

    def phasesequence(self):
        #True means phase sequence and loss monitoring ok.
        self.revpi.readprocimg()
        return self.revpi.io.I_9.value


class tempregulator():
    def __init__(self, factor=1):
        self.setpoint = 1
        self.correction = 0
        self.direction = 'none'
        self.factor = factor

    def update(self, temp, setpoint):
        self.correction = abs(temp - int(setpoint)) * self.factor
        if temp > int(setpoint):
            self.direction = 'up'
        elif temp < int(setpoint):
            self.direction = 'down'
        else:
            self.direction = 'none'
            self.correction = 0

class weatherserver(threading.Thread):
    def __init__(self, db1):
        threading.Thread.__init__(self)
        self.db1 = db1
        
    def run(self):
        while True:
            with urllib.request.urlopen("https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/13.528156/lat/59.921701/data.json") as url:
                data = json.loads(url.read().decode())
                self.db1['data']['weather']['timestamp'] = data['timeSeries'][0]['validTime']
                self.db1['data']['weather']['temperature'] = data['timeSeries'][0]['parameters'][1]['values'][0]
                self.db1['data']['weather']['windspeed'] = data['timeSeries'][0]['parameters'][4]['values'][0]
                self.db1['data']['weather']['winddirection'] = data['timeSeries'][0]['parameters'][3]['values'][0]
                self.db1['data'] = reassign(self.db1['data'])
                transaction.commit()
            sleep(1000)

class webserver(threading.Thread):
    def __init__(self, db1, db2):
        threading.Thread.__init__(self)
        self.db1 = db1
        self.db2 = db2
        app = Flask(__name__, static_url_path='/static')
        app.config['SECRET_KEY'] = 'secret!'
        socketio = SocketIO(app)
        self.socketio = socketio

        @app.route("/")
        def index():
            return render_template('index.html')

        @app.route("/jquery.js")
        def index2():
            return render_template('jquery.js')

        @app.route("/socket.io.min.js")
        def index3():
            return render_template('socket.io.min.js')

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
        motorsyd = ventmotor('O_4', 'O_3', 'I_4', 'I_3', self.io, self.db2, 'motorsyd')
        motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', self.io, self.db2, 'motornord')
        regulator = tempregulator()
        while not self.shutdown_flag.is_set():
            if self.db2['data']['motornord']['ranger'] == 0:
                motornord.testrange()

            #if self.db2['data']['motorsyd']['ranger'] == 0:
            #    motorsyd.testrange()

            if self.db2['data']['VentAutSwitch'] == True:
                regulator.update(23, self.db2['data']['TempSetPointDay'])
                #if self.db2['data']['motorsyd']['ranger'] >
                motornord.moverelativeposition(regulator.correction, regulator.direction)
                logging.debug('Ventilatonserver: Automatiskt läge')
            else:
                motornordposition = int(self.db2['data']['motornord']['movetoposition']) / 100 * self.db2['data']['motornord']['ranger']
                motornord.moveabsoluteposition(int(motornordposition))
                motorsydposition = int(self.db2['data']['motorsyd']['movetoposition']) / 100 * self.db2['data']['motorsyd']['ranger']
                motorsyd.moveabsoluteposition(int(motorsydposition))
                logging.debug('Ventilatonserver: Manuellt läge')

            sleep(3)

        
        print('Setting output to default values')
        modio = revpimodio2.RevPiModIO(autorefresh=False)
        modio.setdefaultvalues()
        modio.writeprocimg()
        
        logging.debug('Ventilatonserver: Avslutar')


def createdatabas(db):
    db['data'] = {  'TempSetPointDay': 20,
                    'VentAutSwitch':   False,
                    
                    'motorsyd': {    'position': 0, 
                                     'movetoposition': 0,
                                     'ranger': 0},

                    'motornord': {   'position': 0, 
                                     'movetoposition': 0,
                                     'ranger': 0},

                    'weather':  {    'timestamp': 0,
                                     'temperature': 0,
                                     'windspeed': 0,
                                     'winddirection': 0}
              }
    transaction.commit()

def signal_handler(signum, frame):
    print('Caught signal %d' % signum)
    raise serviceexit

class serviceexit(Exception):
    pass


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        root = database()
    
        ###updatencomment to create databas###
        db = root.newconn()
        createdatabas(db)

        ventilationserver   = ventilationserver(root.newconn())        
        ventilationserver.start()

        weatherserver       = weatherserver(root.newconn())
        weatherserver.start()

        webserver           = webserver(root.newconn(), root.newconn())
        #webserver.start()

        while True:
            sleep(1)

    except serviceexit:
        ventilationserver.shutdown_flag.set()
        ventilationserver.join()


    #db1 = root.newconn()
    #db1_temp = {}
    #while 1:
    #    sleep(10)
    #    db1_temp['data'] = db1['data']
    #    db1_temp['data']['TempSetPoint'] = 25
    #    db1['data'] = db1_temp['data']
    #    transaction.commit()
    #    sleep(10)
    #    db1_temp['data'] = db1['data']
    #    db1_temp['data']['TempSetPoint'] = 27
    #    db1['data'] = db1_temp['data']
    #    transaction.commit()
    #    sleep(10)
    #    db1_temp['data'] = db1['data']
    #    db1_temp['data']['TempSetPoint'] = 18
    #    db1['data'] = db1_temp['data']
    #    transaction.commit()
    #    sleep(10)
    #    db1_temp['data'] = db1['data']
    #    db1_temp['data']['TempSetPoint'] = 19
    #    db1['data'] = db1_temp['data']
    #    transaction.commit()
