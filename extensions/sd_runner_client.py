from multiprocessing.connection import Client

from utils.config import config
from utils.constants import ImageGenerationType

class SDRunnerClient:
    COMMAND_CLOSE_SERVER = 'close server'
    COMMAND_CLOSE_CONNECTION = 'close connection'
    COMMAND_VALIDATE = 'validate'

    def __init__(self, host='localhost', port=config.sd_runner_client_port):
        self._host = host
        self._port = port
        self._conn = None

    def start(self):
        try:
            self._conn = Client((self._host, self._port), authkey=str.encode(config.sd_runner_client_password))
            print("Started SDRunner Client")
        except Exception as e:
            print(f"Failed to connect to SD Runner: {e}")
            raise e

    def send(self, msg):
        if config.debug:
            print(f"Sending {msg} to SD Runner")
        self._conn.send(msg)
        return self._conn.recv()

    def close(self):
        try:
            self._conn.send(SDRunnerClient.COMMAND_CLOSE_CONNECTION)
            self._conn.close()
            self._conn = None
            print("Closed SD Runner Client")
        except Exception as e:
            print(f"Failed to close SD Runner Client: {e}")
            raise e

    def validate_connection(self):
        try:
            resp = self.send(SDRunnerClient.COMMAND_VALIDATE)
            if resp != 'valid':
                self.close()
                raise Exception(f'SD Runner connection failed validation: {resp}')
        except Exception as e:
            self.close()
            raise Exception(f'Failed to connect to SD Runner: {e}')

    def run(self, _type, base_image):
        if not isinstance(_type, ImageGenerationType):
            raise TypeError(f'{_type} is not a valid ImageGenerationType')
        self.validate_connection()
        try:
            command  = {'command': 'run', 'type': _type.value, 'args': [base_image]}
            resp = self.send(command)
            if "error" in resp:
                raise Exception(f'SD Runner failed to start run {_type} on file {base_image}\n{resp["error"]}: {resp["data"]}')
            print(f"SD Runner started run {_type} on file {base_image}")
            self.close()
            return resp['data'] if "data" in resp else None
        except Exception as e:
            self.close()
            raise Exception(f'Failed to start run on SD Runner: {e}')

    def stop(self):
        self._conn.send(SDRunnerClient.COMMAND_CLOSE_SERVER)
        self._conn.close()

