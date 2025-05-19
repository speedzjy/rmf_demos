import socket
import requests
import time
import json
import os
import threading
from pprint import pprint
from flask import Flask, request, make_response, jsonify


class CDMS:
    def __init__(self, data={}):
        self.data = data
        self.app = Flask(__name__)
        self.setup_routes()
        self.thread_connect_dms = threading.Thread(target=self.run_flask)
        self.thread_connect_dms.daemon = True
        self.thread_connect_dms.start()

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

    def run(self):
        self.thread_connect_dms.join()


data = {}


def main():
    try:
        bridge = CDMS(data)
        bridge.run()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
