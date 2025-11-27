import queue
import threading
from multiprocessing.connection import Client

from utils.config import config
from utils.logging_setup import get_logger

logger = get_logger("refacdir_client")

class RefacDirClient:
    COMMAND_CLOSE_SERVER = 'close server'
    COMMAND_CLOSE_CONNECTION = 'close connection'
    COMMAND_VALIDATE = 'validate'

    def __init__(self, host='localhost', port=config.refacdir_client_port):
        self._host = host
        self._port = port
        self._conn = None
        self._request_queue = queue.Queue()
        self._worker_thread = None
        self._shutdown = False
        self._worker_lock = threading.Lock()

    def start(self):
        try:
            self._conn = Client((self._host, self._port), authkey=str.encode(config.refacdir_client_password))
            logger.info("Started RefacDir Client")
        except Exception as e:
            logger.error(f"Failed to connect to RefacDir: {e}")
            raise e

    def send(self, msg):
        if config.debug:
            logger.debug(f"Sending {msg} to RefacDir")
        self._conn.send(msg)
        return self._conn.recv()

    def close(self):
        try:
            self._conn.send(RefacDirClient.COMMAND_CLOSE_CONNECTION)
            self._conn.close()
            self._conn = None
            logger.info("Closed RefacDir Client")
        except Exception as e:
            logger.error(f"Failed to close RefacDir Client: {e}")
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

    def _start_worker(self):
        """Start the worker thread that processes queued requests (lazy initialization)."""
        with self._worker_lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._shutdown = False
                self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
                self._worker_thread.start()

    def _process_queue(self):
        """Worker thread that processes requests from the queue one at a time."""
        while not self._shutdown:
            try:
                # Get request from queue with timeout to allow checking shutdown flag
                request = self._request_queue.get(timeout=1.0)
                if request is None:  # Shutdown signal
                    break
                
                request_type, args, result_container, condition = request
                
                try:
                    if request_type == 'run':
                        result = self._run_internal(*args)
                        result_container['result'] = result
                except Exception as e:
                    result_container['exception'] = e
                
                result_container['done'] = True
                with condition:
                    condition.notify()
                
                self._request_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in worker thread: {e}")

    def _run_internal(self, base_image):
        """Internal method that performs the actual run operation."""
        self.start()
        self.validate_connection()
        try:
            command  = {'command': 'run', 'args': [base_image]}
            resp = self.send(command)
            if "error" in resp:
                raise Exception(f'RefacDir failed to start run\n{resp["error"]}: {resp["data"]}')
            logger.info(f"RefacDir started run")
            self.close()
            return resp['data'] if "data" in resp else None
        except Exception as e:
            self.close()
            raise Exception(f'Failed to start run on RefacDir: {e}')

    def run(self, base_image):
        """Queue a run request and wait for it to complete."""
        self._start_worker()  # Lazy initialization
        result_container = {'done': False, 'result': None, 'exception': None}
        condition = threading.Condition()
        self._request_queue.put(('run', (base_image,), result_container, condition))
        
        # Wait for completion
        with condition:
            while not result_container['done']:
                condition.wait()
        
        if result_container['exception'] is not None:
            raise result_container['exception']
        
        return result_container['result']

    def stop(self):
        """Stop the worker thread and close the connection."""
        self._shutdown = True
        self._request_queue.put(None)  # Signal shutdown
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
        if self._conn is not None:
            try:
                self._conn.send(RefacDirClient.COMMAND_CLOSE_SERVER)
                self._conn.close()
            except Exception:
                pass

