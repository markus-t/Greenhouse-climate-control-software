import revpimodio2
import signal
from concurrent import futures
from xmlrpc.server import SimpleXMLRPCServer


class RevPiValueServer():
    
    def __init__(self):
        """Init of the class."""
        # RevPiModIO - with monitoring=True so it is ONLY being read!!!
        self.rpi = revpimodio.RevPiModIO(auto_refresh=True, monitoring=True)

        # XMLRPC-Server
        self.xsrv =  SimpleXMLRPCServer(("", 55000), logRequests=False)
        self.xsrv.register_introspection_functions()
        self.xsrv.register_function(self.get_iovalue)

        # Signal events
        signal.signal(signal.SIGINT, self._sigexit)
        signal.signal(signal.SIGTERM, self._sigexit)

    def _sigexit(self, signum=None, frame=None):
        """Handles the exit signal."""
        self.xsrv.shutdown()

    def get_iovalue(self, device, io):
        """Returns a value.
        @param device: Modulename
        @param io: IO-Name
        @returns: IO-Value"""
        if type(io) != str:
            raise ValueError("Work with IO-Names only!")

        io = self.rpi.devices[device][io]
        return io.value

    def start(self):
        """Starts the XMLRPC-Server."""
        e = futures.ThreadPoolExecutor(max_workers=1)
        self._futsrv = e.submit(self.xsrv.serve_forever)
        print("Server started!")
        e.shutdown()


if __name__ == "__main__":
    root = RevPiValueServer()
    root.start()