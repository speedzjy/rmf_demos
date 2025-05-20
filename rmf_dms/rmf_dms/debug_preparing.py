import socket
import requests
import time
import json
import os
import threading
import signal

from pprint import pprint
from flask import Flask, request, make_response, jsonify

from .alog import AsyncLog


class CDMS:
    def __init__(self, data={}):
        self.logger = AsyncLog(self.__class__.__name__)

        self.data = data
        self.app = Flask(__name__)
        self.setup_routes()

        self.exit_event = threading.Event()

    def setup_routes(self):
        @self.app.route("/scheduling", methods=["POST"])
        def scheduling():
            script_dir = os.path.dirname(os.path.abspath(__file__))
            with open(
                os.path.join(script_dir, "test_task.json"), "w", encoding="utf-8"
            ) as file:
                json.dump(
                    json.loads(request.data.decode("utf-8")),
                    file,
                    indent=4,
                    ensure_ascii=False,
                )

            cur_msg = {
                "code": 200,
                "message": "ok",
                "data": [self.data],
            }
            pprint(cur_msg)

            return jsonify(cur_msg)

    def run_flask(self):
        self.app.run(host="0.0.0.0", port=5050, debug=True, use_reloader=False)

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
                    self.logger.info("Tasks sent successfully.")
                    self.logger.info(response.text)
                    self.exit_event.wait(1)
                else:
                    self.logger.info(
                        f"Failed to send tasks. Status code: {response.status_code}"
                    )

            except Exception as e:
                self.logger.info(f"Error sending tasks: {e}")

            self.exit_event.wait(1)

    def run(self):
        self.thread_connect_dms = threading.Thread(target=self.run_flask, daemon=True)
        self.thread_connect_dms.start()

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


data = {}


def main():
    try:
        bridge = CDMS(data)
        bridge.run()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
