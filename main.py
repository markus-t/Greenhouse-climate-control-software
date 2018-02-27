#!/usr/bin/python3
import revpimodio2
import time
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO
from ZODB import FileStorage, DB
import transaction

class ventmotor:
    def __init__(self, go_up, go_down, up_switch, down_switch, io):
        self.go_up = go_up
        self.go_down = go_down
        self.up_switch = up_switch
        self.down_switch = down_switch
        self.position = 0
        self.maxposition = 100
        self.minposition = 0
        self.io = io

    def setmaxposition():
        #
        self.maxposition = 100

    def moveabsoluteposition(self, position):
        if position > self.position:
            self.io.setoutput(self.go_up, True)
            movement = position - self.position
            time.sleep(abs(movement))
            self.io.setoutput(self.go_up, False)
        elif position < self.position:
            self.io.setoutput(self.go_down, True)
            movement = position - self.position
            time.sleep(abs(movement))
            self.io.setoutput(self.go_down, False)
        self.position = position

    def moverelativeposition(self, position, direction):
        if direction == 'up':
            new_position = position + self.position
        else:
            new_position = position - self.position
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
            self.revpi.io.O_3.value = value
        elif output == 'O_2':
            self.revpi.io.O_3.value = value
        elif output == 'O_3':
            self.revpi.io.O_3.value = value
        elif output == 'O_4':
            self.revpi.io.O_4.value = value
        elif output == 'O_5':
            self.revpi.io.O_5.value = value
        elif output == 'O_6':
            self.revpi.io.O_6.value = value
        elif output == 'O_7':
            self.revpi.io.O_7.value = value
        elif output == 'O_8':
            self.revpi.io.O_8.value = value
        print ('set output', output, 'to', value)
    #def watch():
    #    self.revpi.mainloop()

class tempregulator():
    def __init__(self, factor=1):
        self.setpoint = 1
        self.correction = 0
        self.factor = factor
    def update(self, temp, setpoint):
        self.correction = abs(temp - self.setpoint) * self.factor

class webserver():
    def __init__(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'secret!'
        socketio = SocketIO(app)

        @app.route("/")
        def index():
            return render_template('index.html')

        @socketio.on('data_send', namespace='/test')
        def handle_client_connect_event(json):
            print ('Instruktioner mottaget', json)
            #Skicka till databas här

        @socketio.on('connected', namespace='/test')
        def ccl(json):
            print ('Ny användare ansluten', json)

        @app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory('static', path)

        socketio.run(app, host='0.0.0.0', port=5050)
        print ('bajs')

class database():
    def __init__(self):
        storage = FileStorage.FileStorage('database.fs')
        db = DB(storage)
        self.connection = db.open()
    def newconn(self):
        self.root = self.connection.root()

class ventilationserver():
    def __init__(self):
        self.io = io()
        motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', self.io)
        motorsyd = ventmotor('O_3', 'O_4', 'I_3', 'I_4', self.io)
        root = database()
        
        
        regulator = tempregulator()
        while 1:
            regulator.update(21, root['TempSetPoint'])
            #motornord.moverelativeposition(regulator.correction, 'up')
            time.sleep(10)

if __name__ == "__main__":

    webserver = threading.Thread(target=webserver)
    ventilationserver = threading.Thread(target=ventilationserver)
    
    webserver.start()
    ventilationserver.start()
    
