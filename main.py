#!/usr/bin/python3
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=PendingDeprecationWarning)
    import revpimodio2
from time import sleep
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


class ventmotor:
    def __init__(self, go_up, go_down, up_switch, down_switch, io, db2, motor_name):
        self.databas = db2['data']
        self.go_up = go_up
        self.go_down = go_down
        self.up_switch = up_switch
        self.down_switch = down_switch
        self.motor_name = motor_name
        self.databas[motor_name]['maxposition'] = 100
        self.databas[motor_name]['minposition'] = 0
        self.databas[motor_name]['position'] = 0
        self.io = io

    def testrange():

        while down_switch == False:
            self.databas[self.motor_name]['maxposition'] = 100

    def moveabsoluteposition(self, position):
        if position > self.databas[self.motor_name]['position']:
            movement = position - self.databas[self.motor_name]['position']
            logging.debug('Set output %s True for %s seconds', self.go_up, abs(movement))
            self.io.setoutput(self.go_up, True)
            sleep(abs(movement))
            logging.debug('Set output %s False', self.go_up)
            self.io.setoutput(self.go_up, False)

        elif position < self.databas[self.motor_name]['position']:
            movement = position - self.databas[self.motor_name]['position']
            logging.debug('Set output %s True for %s seconds', self.go_up, abs(movement))
            self.io.setoutput(self.go_down, True)
            sleep(abs(movement))
            logging.debug('Set output %s False', self.go_down)
            self.io.setoutput(self.go_down, False)
            
        databas_temp = self.databas[self.motor_name]
        databas_temp['position'] = position
        self.databas[self.motor_name] = databas_temp
        transaction.commit()

    def moverelativeposition(self, position, direction):
        if direction == 'up':
            new_position = position + self.databas[self.motor_name]['position']
        else:
            new_position = position - self.databas[self.motor_name]['position']

        self.moveabsoluteposition(new_position)


class io():
    def __init__(self):
        self.revpi = revpimodio2.RevPiModIO(autorefresh=True)
        #signal.signal(signal.SIGINT, self.exitfunktion)
        #signal.signal(signal.SIGTERM, self.exitfunktion)
        #self.revpi.io.Input.reg_event(self.eventfunktion)

    def eventfunktion(self, ioname, iovalue):
        #self.revpi.io.Output.value = iovalue
        print(time.time(), ioname, iovalue)

    def exitfunktion(self):
        # Turn off LED A1 on the Core
        print('Exiting')
        self.revpi.core.A1 = revpimodio2.OFF

    def setoutput(self, output, value):
        if output == 'O_1':
            self.revpi.io.O_1.value = value
        elif output == 'O_2':
            self.revpi.io.O_2.value = value
        elif output == 'O_3':
            self.revpi.io.O_3.value = value
        elif output == 'O_4':
            self.revpi.io.O_4.value = value
        sleep(1)


    def getoutput(self, output):
        if output == 'I_1':
            return self.revpi.io.I_1.value
        elif output == 'I_2':
            return self.revpi.io.I_2.value
        elif output == 'I_3':
            return self.revpi.io.I_3.value
        elif output == 'I_4':
            return self.revpi.io.I_4.value
        sleep(1)

    #def watch():
    #    self.revpi.mainloop()

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


class webserver():
    def __init__(self, db1, db2):
        self.db1 = db1
        self.db2 = db2
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'secret!'
        socketio = SocketIO(app)
        self.socketio = socketio
        @app.route("/")
        def index():
            return render_template('index.html')

        @socketio.on('data_send', namespace='/test')
        def handle_client_connect_event(json):
            temp = {}
            logging.debug('Webserver: Sparar JSON data: %s', json)
            print(self.db1['data'])
            for key in json:
                if type(json[key]) is dict:
                    for key2 in json[key]:
                        self.db1['data'][key][key2] = json[key][key2]
                else:
                    self.db1['data'][key] = json[key]
            temp['data'] = self.db1['data']
            self.db1['data'] = temp['data']
            transaction.commit()

        @socketio.on('connected', namespace='/test')
        def ccl(json):
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
            self.socketio.sleep(10)
            if self.db1_comp2['data'] != self.db2['data']:
                logging.debug('Webserver: skickar ny data till webbläsare')
                self.socketio.emit('my_response', self.db2['data'],
                                    namespace='/test')

                self.db1_comp2['data'] = deepcopy(self.db2['data'])
                


class database():
    def __init__(self):
        storage = FileStorage.FileStorage('database.fs')
        db = DB(storage)
        self.connection = db.open()
        
    def newconn(self):
        return self.connection.root()

class ventilationserver():
    def __init__(self, db2):
        self.io = io()
        #print(self.io.getoutput('I_1'))
        motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', self.io, db2, 'motornord')
        motorsyd = ventmotor('O_3', 'O_4', 'I_3', 'I_4', self.io, db2, 'motorsyd')
        
        regulator = tempregulator()
        while 1:
            if db2['data']['VentAutSwitch'] == True:
                regulator.update(23, db2['data']['TempSetPointDay'])
                print (regulator.correction)
                print (regulator.direction)
                motornord.moverelativeposition(regulator.correction, regulator.direction)
                logging.debug('Ventilatonserver: Automatiskt läge')
            else:
                motornord.moveabsoluteposition(int(db2['data']['motornord']['movetoposition']))
                motorsyd.moveabsoluteposition(int(db2['data']['motorsyd']['movetoposition']))
                logging.debug('Ventilatonserver: Manuellt läge')
            sleep(3)

def createdatabas(db):
    db['data'] = {  'TempSetPointDay': 20,
                    'VentAutSwitch':   True,
                    
                    'motorsyd': {    'position': 0, 
                                     'movetoposition': 0,
                                     'minposition': 0, 
                                     'maxposition': 0},

                    'motornord': {   'position': 0, 
                                     'movetoposition': 0,
                                     'minposition': 0, 
                                     'maxposition': 0}
              }
    transaction.commit()


if __name__ == "__main__":
    root = database()
    
    ###Uncomment to create databas###
    #db = root.newconn()
    #createdatabas(db)
    
    webserver = threading.Thread(target=webserver, args=(root.newconn(),root.newconn(),))
    ventilationserver = threading.Thread(target=ventilationserver, args=(root.newconn(),))
    
    webserver.start()
    ventilationserver.start()

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
