import socket
import requests
import time
import json
import os
import threading
import signal

from pprint import pprint

from .alog import AsyncLog


class TaskSender:
    def __init__(self):
        self.logger = AsyncLog(self.__class__.__name__)
        self.exit_event = threading.Event()

    def run_send_tasks(self):
        url = "http://localhost:6060/tasks"
        headers = {"Content-Type": "application/json"}
        while not self.exit_event.is_set():
            try:
                with open(
                    os.path.join(os.path.dirname(__file__), "tasks", "task_1.json"),
                    "r",
                    encoding="utf-8",
                ) as f:
                    data = json.load(f)

                response = requests.post(url, headers=headers, json=data)

                if response.status_code == 200:
                    self.logger.info(response.text)
                    self.exit_event.wait(9)
                else:
                    self.logger.info(
                        f"Failed to send tasks. Status code: {response.status_code}"
                    )

            except Exception as e:
                self.logger.info(f"Error sending tasks: {e}")

            self.exit_event.wait(1)

    def run(self):
        self.thread_send_tasks = threading.Thread(
            target=self.run_send_tasks, daemon=True
        )
        self.thread_send_tasks.start()

        def _signal_handler(sig, frame):
            print("\n")
            self.exit_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        while not self.exit_event.is_set():
            time.sleep(0.5)

        self.logger.info("Program terminated.")


def main():
    try:
        bridge = TaskSender()
        bridge.run()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
