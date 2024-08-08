from multiprocessing.connection import Client

from utils.config import config
from utils.utils import Utils

class RefacDirClient:
    COMMAND_CLOSE_SERVER = 'close server'
    COMMAND_CLOSE_CONNECTION = 'close connection'
    COMMAND_VALIDATE = 'validate'

    def __init__(self, host='localhost', port=config.refacdir_client_port):
        self._host = host
        self._port = port
        self._conn = None

    def start(self):
        try:
            self._conn = Client((self._host, self._port), authkey=str.encode(config.refacdir_client_password))
            Utils.log("Started RefacDir Client")
        except Exception as e:
            Utils.log_red(f"Failed to connect to RefacDir: {e}")
            raise e

    def send(self, msg):
        if config.debug:
            Utils.log_debug(f"Sending {msg} to RefacDir")
        self._conn.send(msg)
        return self._conn.recv()

    def close(self):
        try:
            self._conn.send(RefacDirClient.COMMAND_CLOSE_CONNECTION)
            self._conn.close()
            self._conn = None
            Utils.log("Closed RefacDir Client")
        except Exception as e:
            Utils.log_red(f"Failed to close RefacDir Client: {e}")
            raise e

    def validate_connection(self):
        try:
            resp = self.send(RefacDirClient.COMMAND_VALIDATE)
            if resp != 'valid':
                self.close()
                raise Exception(f'RefacDir connection failed validation: {resp}')
        except Exception as e:
            self.close()
            raise Exception(f'Failed to connect to RefacDir: {e}')

    def run(self, base_image):
        self.validate_connection()
        try:
            command  = {'command': 'run', 'args': [base_image]}
            resp = self.send(command)
            if "error" in resp:
                raise Exception(f'RefacDir failed to start run\n{resp["error"]}: {resp["data"]}')
            Utils.log(f"RefacDir started run")
            self.close()
            return resp['data'] if "data" in resp else None
        except Exception as e:
            self.close()
            raise Exception(f'Failed to start run on RefacDir: {e}')

    def stop(self):
        self._conn.send(RefacDirClient.COMMAND_CLOSE_SERVER)
        self._conn.close()

