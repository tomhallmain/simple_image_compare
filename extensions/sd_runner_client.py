from multiprocessing.connection import Client

from image.image_data_extractor import image_data_extractor
from utils.config import config
from utils.constants import ImageGenerationType
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("sd_runner_client")

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
            logger.info("Started SDRunner Client")
        except Exception as e:
            logger.error(f"Failed to connect to SD Runner: {e}")
            raise e

    def send(self, msg):
        if config.debug:
            logger.debug(f"Sending {msg} to SD Runner")
        self._conn.send(msg)
        return self._conn.recv()

    def close(self):
        try:
            self._conn.send(SDRunnerClient.COMMAND_CLOSE_CONNECTION)
            self._conn.close()
            self._conn = None
            logger.info("Closed SD Runner Client")
        except Exception as e:
            logger.error(f"Failed to close SD Runner Client: {e}")
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

    def validate_image_for_type(self, _type, base_image):
        if _type == ImageGenerationType.REDO_PROMPT:
            prompt, software_type = image_data_extractor.extract_prompt(base_image)
            if prompt is None:
                self.close()
                raise Exception(_('Image does not contain a prompt to redo!'))

    def run(self, _type, base_image, append=False):
        if not isinstance(_type, ImageGenerationType):
            raise TypeError(f'{_type} is not a valid ImageGenerationType')
        self.validate_image_for_type(_type, base_image)
        self.validate_connection()
        try:
            command  = {'command': 'run', 'type': _type.value,
                        'args': {'image': base_image, 'append': append}}
            resp = self.send(command)
            if "error" in resp:
                self.close()
                raise Exception(f'SD Runner failed to start run {_type} on file {base_image}\n{resp["error"]}: {resp["data"]}')
            logger.info(f"SD Runner started run {_type} on file {base_image}")
            self.close()
            return resp['data'] if "data" in resp else None
        except Exception as e:
            try:
                self.close()
            except Exception as e2:
               pass
            raise Exception(f'Failed to start run on SD Runner: {e}')

    def stop(self):
        self._conn.send(SDRunnerClient.COMMAND_CLOSE_SERVER)
        self._conn.close()

