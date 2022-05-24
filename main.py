#!/usr/bin/python3
# -*- coding: iso-8859-15 -*-
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=PendingDeprecationWarning)
    import revpimodio2
from time import sleep, time
import datetime
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
from multiprocessing import Process, Manager
import os
import transaction
import ZODB.config

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

def reassign(ordbok):
    temp = {}
    temp = ordbok
    return temp

def cyclewait():
    sleep(0.2)

class ventmotor:
    def __init__(self, go_up, go_down, up_switch, down_switch, io, db2, motor_name):
        self.db2 = db2
        self.data = db2['data']
        self.motor = db2['data'][motor_name]
        self.go_up = go_up
        self.go_down = go_down
        self.up_switch = up_switch
        self.down_switch = down_switch
        self.io = io
        self.rangemargin = 1

    def reinit(self):
        self.io.setoutput(self.go_down, True) 
        self.io.setoutput(self.go_up, False)  
        cyclewait()      
        while self.io.getoutput(self.down_switch) == True:
            sleep(0.5)
            logging.debug('Ventmotor: reinit, go down')

        self.io.setoutput(self.go_down, False) 
        self.io.setoutput(self.go_up, False)

        logging.debug('Window down confirmed, resetting.')
        self.motor['position'] = 0
        self.db2['data'] = reassign(self.db2['data'])
        transaction.commit()

    def cleanstate(self):
        if self.motor['cleanstate'] is True:
            logging.debug('Motor is in clean state')
            return True
        else:
            logging.debug('Motor is not in clean state')
            self.reinit() 
            self.motor['cleanstate'] = True
            self.db2['data'] = reassign(self.db2['data'])
            transaction.commit()
            return False

    def verifyposition(self, position):
        if position > self.motor['ranger']:
            logging.debug('Position higher than range')
            return False

        if position < 0:
            logging.debug('Position lower than range')
            return False

        movement = abs(position - self.originposition)

        if movement < 2 and position != 0:
            logging.debug('Movement to little')
            return False

        if position == 0 and self.originposition == 0:
            logging.debug('Motor is already closed')
            return False

        logging.debug('Position in range')
        return True

    def phasesequence(self):
        if self.io.phasesequence() is True:
            logging.warning('Phasesequence fail')
            return False
        return True

    def goup(self, run):
        if run == True:
            self.io.setoutput(self.go_up, True)
        else:
            self.io.setoutput(self.go_up, False)


    def godown(self, run):
        if run == True:
            self.io.setoutput(self.go_down, True)
        else:
            self.io.setoutput(self.go_down, False)

    def moveabsoluteposition(self, position):
        
        if self.cleanstate() is False:
            return False

        self.originposition = self.motor['position']

        movement = abs(position - self.originposition)
        if self.verifyposition(position) is False:
            return False

        for attempt in transaction.manager.attempts():
            with attempt:
                self.motor['cleanstate'] = False
                self.db2['data'] = reassign(self.db2['data'])

        #Lägg till frysgraderkontroll

        if position > self.originposition:
            go_up = True
            lagg = self.motor['uplag']
            logging.debug('Set output %s True for %s seconds', self.go_up, movement)
            self.io.setoutput(self.go_up, True)

        elif position <= self.originposition:
            go_up = False
            lagg = self.motor['downlag']
            logging.debug('Set output %s True for %s seconds', self.go_down, movement)
            self.io.setoutput(self.go_down, True)

        endtime = time() + movement - lagg
        now = time()
        sleep(0.1)
        down_position_reset = False

        while True:
            sleep (0.1)
            if endtime < time():
                if position is not 0 or go_up is True:
                    logging.debug('Finished running motor')
                    break

            #Lagg till timeout ifall inte luckans stängs alls.

            if self.phasesequence() is False:
                break

            #Lg till fungerande logik vid vre momentbrytare
            if self.io.getoutput(self.up_switch) is False and go_up is True:
                logging.info('Up moment switch fail')
                break

            if self.io.getoutput(self.down_switch) is False and go_up is False:
                logging.info('Down Moment switch on at position %s, resetting', self.originposition - (time() - now))
                down_position_reset = True
                break

        if go_up is True:
            logging.debug('Set output %s False', self.go_up)
            self.io.setoutput(self.go_up, False)
            new_position = self.originposition + (time() - now) + lagg
            self.motor['upcount'] = self.motor['upcount'] + 1
            
        elif go_up is False:
            logging.debug('Set output %s False', self.go_down)
            self.io.setoutput(self.go_down, False)
            new_position = self.originposition - (time() - now) - lagg
            self.motor['downcount'] = self.motor['downcount'] + 1
        
        for attempt in transaction.manager.attempts():
            with attempt:
                self.motor['cleanstate'] = True
                if down_position_reset:
                    self.motor['position'] = 0
                    self.motor['downcount'] = 0
                    self.motor['upcount'] = 0
                else:
                    self.motor['position'] = new_position
                self.db2['data'] = reassign(self.db2['data'])


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
            self.revpi.io.O_14.value = value
        elif output == 'L':
            self.revpi.io.O_13.value = value
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
            val = self.revpi.io.Input_Word_2.value
            if val >= 32768:
                return int((val - 65536) / 10)
            return int(val / 10)
        elif output == 'lux':
            return self.revpi.io.Input_Word_1.value / 10
        elif output == 'hum':
            return int(self.revpi.io.Input_Word_3.value / 10)


    def phasesequence(self):
        #True means phase sequence and loss monitoring ok.
        self.revpi.readprocimg()
        return self.revpi.io.I_9.value


class tempregulator():
    def __init__(self, factor=5):
        self.setpoint = 1
        self.correction = 0
        self.new_position = 0
        self.direction = 'none'
        self.factor = factor

    def update(self, temp, setpoint, position):
        self.correction = abs(temp - int(setpoint)) * self.factor
        if temp - 1 > int(setpoint):
            self.direction = 'up'
            self.new_position = position + self.correction
        elif temp + 1 < int(setpoint):
            self.direction = 'down'
            self.new_position = position - self.correction
        else:
            self.direction = 'none'
            self.correction = 0

class weatherserver(threading.Thread):
    def __init__(self, db1):
        threading.Thread.__init__(self)
        self.daemon = True
        self.weather = db1['data']['weather']
        self.db1 = db1
        
    def run(self):
        while True:
            with urllib.request.urlopen("https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/13.528156/lat/59.921701/data.json") as url:
                data = json.loads(url.read().decode())
                self.weather['timestamp'] = data['timeSeries'][0]['validTime']

                for value in data['timeSeries'][0]['parameters']:
                    if value['name'] == 't':
                        self.weather['temperature'] = value['values'][0]
                    if value['name'] == 'gust':
                        self.weather['windspeed'] = value['values'][0]
                    if value['name'] == 'wd':
                        self.weather['winddirection'] = value['values'][0]
                    if value['name'] == 'r':
                        self.weather['humudity'] = value['values'][0]
                    if value['name'] == 'tcc_mean':
                        self.weather['cloudness'] = value['values'][0]
                for attempt in transaction.manager.attempts():
                    with attempt:
                        self.db1['data'] = reassign(self.db1['data'])
            sleep(1000)

class sensorsync(threading.Thread):
    def __init__(self, db1, io):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db1 = db1
        self.data = db1['data']
        self.logg = db1['logg']
        self.io = io
        
    def run(self):
        while True:
            for attempt in transaction.manager.attempts():
                with attempt:
                    logging.debug('Sensorsync: sync')
                    self.data['lux'] = self.io.getoutput('lux')
                    self.data['hum'] = self.io.getoutput('hum')
                    self.data['deg'] = self.io.getoutput('deg')
                    if not self.logg['deg_history'] or self.logg['deg_history'][-1]['deg'] != self.data['deg']:
                        now = datetime.datetime.now().replace(microsecond=0).isoformat()
                        a = datetime.datetime.now()
                        self.logg['deg_history'].append({'date': now, 'deg': self.io.getoutput('deg'), 'year': a.year, 'month': a.month, 'day': a.day, 'hour': a.hour, 'minute': a.minute})

                    self.db1['data'] = reassign(self.db1['data'])
                    #NY
                    transaction.commit()
                    #print(self.db1['data'])
            sleep(120)

class webserver(threading.Thread):
    def __init__(self, db1, db2):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db1 = db1
        self.db2 = db2

    def run(self):
        app = Flask(__name__, static_url_path='/static')
        app.config['SECRET_KEY'] = 'secret!'
        socketio = SocketIO(app)
        self.socketio = socketio

        @app.route("/")
        def index():
            return render_template('index.html')

        @app.route("/debug")
        def debug(): 
            return str(self.db1)
            
        @app.route("/logg")
        def logg(): 
            rows = list()
            for row in self.db1['logg']['deg_history']:
            	var = "Date({}, {}, {}, {}, {})".format(row['year'], row['month'], row['day'], row['hour'], row['minute'])
            	rows.append({'c':[{"v":var,"f":var}, {"v":row['deg'],"f":row['deg']}]})


            var = json.dumps(       {'cols': [
                                        {'id':"","label":"Timme","pattern":"","type":"datetime"}, 
                                        {'id':"","label":"Temperatur","pattern":"","type":"number"}], 
                                    'rows': rows
                                        })
            return var

        @socketio.on('data_send', namespace='/test')
        def handle_client_connect_event(json):
            for attempt in transaction.manager.attempts():
                with attempt:
                    logging.debug('Webserver: Sparar JSON data: %s', json)
                    for key in json:
                        if type(json[key]) is dict:
                            for key2 in json[key]:
                                if type(json[key][key2]) is dict:
                                    for key3 in json[key][key2]:
                                        self.db1['data'][key][key2][key3] = json[key][key2][key3]
                                else:
                                        self.db1['data'][key][key2] = json[key][key2]
                        else:
                            self.db1['data'][key] = json[key]
                    self.db1['data'] = reassign(self.db1['data'])
                    #NY
                    self.db1._p_changed = True
                    transaction.commit()
                    print("HEJ")

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
        db1_comp = {}
        db1_comp['data'] = deepcopy(self.db2['data'])
    
        while True:
            self.socketio.sleep(1)
            if db1_comp['data'] != self.db2['data']:
                logging.debug('Webserver: skickar ny data till webbläsare')
                self.socketio.emit('my_response', self.db2['data'], namespace='/test')

                db1_comp['data'] = deepcopy(self.db2['data'])

#ändra till sql databas!
class database():   
    def __init__(self): 
        storage = FileStorage.FileStorage('database.fs')    
        db = DB(storage)    
        self.dba = db   
        db.pack()   
        self.connection = db.open() 
            
    def newconn(self):  
        return self.connection.root()

class ventilationserver(threading.Thread):
    def __init__(self, db2):
        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()
        self.conn = db2
        self.db2 = db2.newconn()
        self.data = self.db2['data']
        self.io = io()

    def heater(self):
        self.io.setoutput('L', True)
        if int(self.data['TempSetPointHeater']) < self.data['deg'] or self.data['HeaterSwitch'] is False:
            print('Setting heater off')
            self.io.setoutput('H', False)    
        elif int(self.data['TempSetPointHeater']) + 1 > self.data['deg'] and self.data['HeaterSwitch'] is True:          
            print('Setting heater on')
            self.io.setoutput('H', True)

        W1 = {}
        W2 = {}
        now = datetime.datetime.now()
        for value in self.data['watering']:
            difference =  datetime.datetime.strptime(self.data['watering'][value]['starttime'], '%H:%M') + datetime.timedelta(minutes=int(self.data['watering'][value]['wateringtime']))
            if datetime.datetime.strptime(self.data['watering'][value]['starttime'], '%H:%M').time() < now.time() < difference.time():
                if self.data['watering'][value]['W1']:
                    W1[value] = True
                else:
                    W1[value] = False

                if self.data['watering'][value]['W2']:
                    W2[value] = True
                else:
                    W2[value] = False
            else:
                W1[value] = False
                W2[value] = False

        if W1['A'] or W1['B'] or W1['C'] or W1['D']:
            print('Set W1 True')
            self.io.setoutput('W1', True)
        else:
            self.io.setoutput('W1', False)
            print('Set W1 False')

        if W2['A'] or W2['B'] or W2['C'] or W2['D']:
            self.io.setoutput('W2', True)
            print('Set W2 True')
        else:
            self.io.setoutput('W2', False)
            print('Set W2 False')

 

    def run(self):
        motorsyd = ventmotor('O_3', 'O_4', 'I_3', 'I_4', self.io, self.db2, 'motorsyd')
        motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', self.io, self.db2, 'motornord')
        regulatorsyd = tempregulator()
        regulatornord = tempregulator()
     
        while not self.shutdown_flag.is_set():            

            if self.data['VentAutSwitch'] is True:
                time_u = time()
                while self.data['VentAutSwitch'] is True and self.shutdown_flag.is_set() == False:

                    if self.data['weather']['winddirection'] > 90 and self.db2['data']['weather']['winddirection'] < 270:
                        leeside = 'nord'
                    else:
                        leeside = 'syd'

                    if self.data['weather']['windspeed'] > 16:
                        leeside_factor  = 0
                        windside_factor = 0
                    elif self.data['weather']['windspeed'] > 14:
                        leeside_factor = 0.70
                        windside_factor = 0.20
                    elif self.data['weather']['windspeed'] > 12:
                        leeside_factor  = 0.90
                        windside_factor = 0.40
                    elif self.data['weather']['windspeed'] > 10:
                        leeside_factor  = 1
                        windside_factor = 0.70
                    else:
                        leeside_factor  = 1
                        windside_factor = 1

                    if time_u + 300 < time():    
                        regulatornord.update(self.io.getoutput('deg'), self.data['TempSetPointDay'], self.data['motornord']['position'])
                        regulatorsyd.update(self.io.getoutput('deg'), self.data['TempSetPointDay'], self.data['motorsyd']['position'])

                        if self.data['hum'] > 80 and True is True and self.data['deg'] > 12:
                            nattluft = True
                        else:
                            nattluft = False

                        if leeside == 'nord':
                            nord_max_position = self.data['motornord']['ranger'] * leeside_factor
                            syd_max_position = self.data['motorsyd']['ranger'] * windside_factor
                            if nattluft:
                                nord_min_position = 25 * leeside_factor
                                syd_min_position = 25 * windside_factor
                            else:
                                nord_min_position = 0
                                syd_min_position = 0
                        else:
                            nord_max_position = self.data['motornord']['ranger'] * windside_factor
                            syd_max_position = self.data['motorsyd']['ranger'] * leeside_factor
                            if nattluft:
                                nord_min_position = 25 * windside_factor
                                syd_min_position = 25 * leeside_factor
                            else:
                                nord_min_position = 0
                                syd_min_position = 0

                        if regulatornord.new_position > nord_max_position:
                            nord_new_position = nord_max_position
                        elif regulatornord.new_position < nord_min_position:
                            nord_new_position = nord_min_position
                        elif regulatornord.new_position < 0:
                            nord_new_position = 0
                        else:
                            nord_new_position = regulatornord.new_position

                        if regulatorsyd.new_position > syd_max_position:
                            syd_new_position = syd_max_position
                        elif regulatorsyd.new_position < syd_min_position:
                            syd_new_position = syd_min_position
                        elif regulatorsyd.new_position < 0:
                            syd_new_position = 0
                        else:
                            syd_new_position = regulatorsyd.new_position


                        logging.debug('Ventilatonserver: motorsyd ny begränsad position: %s ', syd_new_position)
                        logging.debug('Ventilatonserver: motornord ny begränsad position: %s ', nord_new_position)
                        motornord.moveabsoluteposition(nord_new_position)
                        motorsyd.moveabsoluteposition(syd_new_position)

                        time_u = time()

                    self.heater()

                    if self.data['motornord']['movetoposition'] != self.data['motornord']['position'] or self.data['motornord']['movetoposition'] != self.data['motornord']['position']:
                        for attempt in transaction.manager.attempts():
                            with attempt:
                                self.data['motornord']['movetoposition'] = self.data['motornord']['position']
                                self.data['motornord']['movetoposition'] = self.data['motornord']['position']
                                self.db2['data'] = reassign(self.db2['data'])

                    logging.debug('Ventilatonserver: Automatiskt läge')
                    sleep(0.5)
            else:
                motornordposition = int(self.data['motornord']['movetoposition']) / 100 * self.data['motornord']['ranger']
                motornord.moveabsoluteposition(int(motornordposition))
                motorsydposition = int(self.data['motorsyd']['movetoposition']) / 100 * self.data['motorsyd']['ranger']
                motorsyd.moveabsoluteposition(int(motorsydposition))
                logging.debug('Ventilatonserver: Manuellt läge')
                self.heater()
                self.conn.pack()
                sleep(1)
        
        logging.info('Ventilatonserver: Avslutad')


def createdatabas(db):
    db['logg'] = {  'deg_history': [ ]}
    db['data'] = {  'TempSetPointDay': 22,
                    'TempSetPointHeater': 1,
                    'VentAutSwitch':   True,
                    'HeaterSwitch':   True,
                    'deg' : 0,
                    'hum': 0,
                    'lux': 0,                    
                    'motorsyd': {    'position': 0,
                                     'downlag': 0.36,
                                     'uplag': 0.14, 
                                     'movetoposition': 0,
                                     'halt': False,
                                     'upcount': 0,
                                     'downcount': 0,
                                     'cleanstate': True,
                                     'ranger': 160},

                    'motornord': {   'position': 0, 
                                     'downlag': 0.60,
                                     'uplag': 0.16, 
                                     'movetoposition': 0,
                                     'halt': False,
                                     'upcount': 0,
                                     'downcount': 0,
                                     'cleanstate': True,
                                     'ranger': 160},

                    'watering': {    'A': { 'starttime': '00:00',
                                            'wateringtime': 1380,
                                            'W1': False,
                                            'W2': False}, 
                                     'B': { 'starttime': '00:00',
                                            'wateringtime': 5,
                                            'W1': False,
                                            'W2': False}, 
                                     'C': { 'starttime': '00:00',
                                            'wateringtime': 5,
                                            'W1': False,
                                            'W2': False}, 
                                     'D': { 'starttime': '00:00',
                                            'wateringtime': 5,
                                            'W1': False,
                                            'W2': False}, 
                                     },

                    'weather':  {    'timestamp': 0,
                                     'temperature': 0,
                                     'windspeed': 0,
                                     'cloudness': 0,
                                     'humudity': 0,
                                     'winddirection': 0}
              }
    transaction.commit()



def runner():
    os.nice(5)
    global ventilationserver
    global weatherserver
    global sensorsync
    global webserver

    root = database()
    
    ###updatencomment to create databas###
    #db = root.newconn()
    #createdatabas(db)

    webserver           = webserver(root.newconn(), root.newconn())
    webserver.start()

    ventilationserver   = ventilationserver(root)        
    ventilationserver.start()

    weatherserver       = weatherserver(root.newconn())
    weatherserver.start()

    sensorsync       = sensorsync(root.newconn(), io())
    sensorsync.start()

    while True:
        sleep(10)
        #print(root.newconn())

    ventilationserver.shutdown_flag.set()
    ventilationserver.join()



if __name__ == "__main__":
    runner()
