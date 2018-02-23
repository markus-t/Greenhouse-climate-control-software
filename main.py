#!/usr/bin/python3
import revpimodio2
import time
import PID

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

    def defineMaxPosition():
        #öppna ventilationen tills övermomentskretsen löser ut.
        self.maxposition = 100

    def moveToPosition(self, position):
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


class io():
    def __init__(self):
        self.revpi = revpimodio2.RevPiModIO(autorefresh=True)
        self.revpi.handlesignalend(self.exitfunktion)
        self.revpi.io.Input.reg_event(self.eventfunktion)

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
    def watch():
        self.revpi.mainloop()


if __name__ == "__main__":
    root = io()
    motornord = ventmotor('O_1', 'O_2', 'I_1', 'I_2', root)
    motorsyd = ventmotor('O_3', 'O_4', 'I_3', 'I_4', root)


    pid = PID.PID(2, 0.1, 0.0)
    pid.SetPoint = 21
    pid.update(20)
    time.sleep(1)
    while 1:
        with open('temp', 'r') as myfile:
            temp=myfile.read().replace('\n', '')
            temp = int(temp)
        pid.update(temp)
        motornord.moveToPosition(pid.output)
        print ('PID Output', pid.output)
        print ('PID PV', temp)
        print ('--')
        time.sleep(5)
