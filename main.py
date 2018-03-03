#!/usr/bin/python3
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=PendingDeprecationWarning)
    import revpimodio2
import time
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO
from ZODB import FileStorage, DB
import transaction
import json
import logging, sys
from pprint import pprint


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
            logging.debug('Set output %s True', self.go_up)
            self.io.setoutput(self.go_up, True)
            movement = position - self.databas[self.motor_name]['position']
            time.sleep(abs(movement))
            logging.debug('Set output %s False', self.go_up)
            self.io.setoutput(self.go_up, False)

        elif position < self.databas[self.motor_name]['position']:
            logging.debug('Set output %s False', self.go_down)
            self.io.setoutput(self.go_down, True)
            movement = position - self.databas[self.motor_name]['position']
            time.sleep(abs(movement))
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
    #    self.revpi.handlesignalend(self.exitfunktion)
    #    self.revpi.io.Input.reg_event(self.eventfunktion)

    def eventfunktion(self, ioname, iovalue):
        self.revpi.io.Output.value = iovalue
        print(time.time(), ioname, iovalue)

    def exitfunktion(self):
        # Turn off LED A1 on the Core
        self.revpi.core.A1 = revpimodio2.OFF

    def setoutput(self, output, value):
        # Set LED A1 at Core to green
        self.revpi.core.A1 = 1
        if output == 'O_1':
            self.revpi.io.O_1.value = value
        elif output == 'O_2':
            self.revpi.io.O_2.value = value
        elif output == 'O_3':
            self.revpi.io.O_3.value = value
        elif output == 'O_4':
            self.revpi.io.O_4.value = value
        time.sleep(2)
        print(self.revpi.io.I_4.value)
        time.sleep(2)


    def getoutput(self, output):
        if output == 'I_1':
            return self.revpi.io.I_1.value
        elif output == 'I_2':
            return self.revpi.io.I_2.value
        elif output == 'I_3':
            return self.revpi.io.I_3.value
        elif output == 'I_4':
            return self.revpi.io.I_4.value

    #def watch():
    #    self.revpi.mainloop()

class tempregulator():
    def __init__(self, factor=1):
        self.setpoint = 1
        self.correction = 0
        self.direction = 'up'
        self.factor = factor
    def update(self, temp, setpoint):
        self.correction = abs(temp - self.setpoint) * self.factor
        if temp > setpoint:
            self.direction = 'up'
        elif temp < setpoint:
            self.direction = 'down'
        else:
            self.direction = 'none'
            self.correction = 0


class webserver():
    def __init__(self, db1):
        self.db1 = db1
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'secret!'
        socketio = SocketIO(app)
        self.socketio = socketio
        @app.route("/")
        def index():
            return render_template('index.html')

        @socketio.on('data_send', namespace='/test')
        def handle_client_connect_event(json):
            print ('Webserver: Sparar JSON Data: ', json)
            for key in json:
                db1[key] = json[key]

        @socketio.on('connected', namespace='/test')
        def ccl(json):
            print ('Webbserver: Ny anvandare ansluten', json)

        @app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory('static', path)

        self.thread = socketio.start_background_task(target=self.push_updates_thread)

        socketio.run(app, host='0.0.0.0', port=5050)
    
    def push_updates_thread(self):
        db1_comp = {}
        db1_comp['data'] = dict(self.db1['data'])
        while True:
            time.sleep(2)
            if db1_comp['data'] != self.db1['data']:
                self.socketio.emit('my_response', db1['data'],
                                    namespace='/test')
                logging.debug(db1['data'])
                db1_comp['data'] = dict(self.db1['data'])


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
        print(self.io.getoutput('I_1'))
        motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', self.io, db2, 'motornord')
        motorsyd = ventmotor('O_3', 'O_4', 'I_3', 'I_4', self.io, db2, 'motorsyd')
        
        regulator = tempregulator()
        while 1:
            regulator.update(23, db2['data']['TempSetPoint'])
            motornord.moverelativeposition(regulator.correction, regulator.direction)
            time.sleep(1)

def createdatabas(db):
    db['data'] = {  'TempSetPoint': 20,
            'motorsyd': {    'position': 0, 
                             'minposition': 0, 
                             'maxposition': 0},
            'motornord': {   'position': 0, 
                             'minposition': 0, 
                             'maxposition': 0}
              }
    transaction.commit()


if __name__ == "__main__":
    root = database()
    
    ###Uncomment to create databas###
    #db = root.newconn()
    #createdatabas(db)
    
    webserver = threading.Thread(target=webserver, args=(root.newconn(),))
    ventilationserver = threading.Thread(target=ventilationserver, args=(root.newconn(),))
    
    webserver.start()
    ventilationserver.start()
 

    db1 = root.newconn()
    db1_temp = {}
    while 1:
        time.sleep(5)
        db1_temp['data'] = db1['data']
        db1_temp['data']['TempSetPoint'] = 25
        db1['data'] = db1_temp['data']
        transaction.commit()
        time.sleep(5)
        db1_temp['data'] = db1['data']
        db1_temp['data']['TempSetPoint'] = 27
        db1['data'] = db1_temp['data']
        transaction.commit()
        time.sleep(5)
        db1_temp['data'] = db1['data']
        db1_temp['data']['TempSetPoint'] = 18
        db1['data'] = db1_temp['data']
        transaction.commit()
        time.sleep(5)
        db1_temp['data'] = db1['data']
        db1_temp['data']['TempSetPoint'] = 19
        db1['data'] = db1_temp['data']
        transaction.commit()
