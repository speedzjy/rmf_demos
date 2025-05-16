#!/usr/bin/env python3

# Copyright 2025 junyi zhou
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import uuid
import argparse
import json
import asyncio
import math
import logging
import threading
import time
import requests
import aiohttp
import signal
import uvicorn

from fastapi import FastAPI, File, UploadFile


from flask import Flask, request, make_response, jsonify
from collections import defaultdict

from .alog import AsyncLog
from .workstation import Workstation


class FakeDms:
    def __init__(self):
        # --------------------日志设置-----------------------------
        self.logger = AsyncLog(self.__class__.__name__)
        # -------------------------------------------------------

        # --------------------FastAPI后端--------------------------
        self.app = FastAPI()
        self.setup_routes()
        # -------------------------------------------------------

        self.exit_event = threading.Event()

    def setup_routes(self):
        @self.app.get("/")
        async def hello():
            return "Hello, World!"

    def run_faskapi(self, port=6060):
        # log = logging.getLogger("werkzeug")
        # log.setLevel(logging.CRITICAL)
        # print(f"\n\033[92m * Flask app is starting on port: {port}\033[0m")
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            debug=True
        )

    def signal_handler(self, sig, frame):
        print("\n")
        self.exit_event.set()

    def run(self):
        self.thread_connect_dms = threading.Thread(target=self.run_faskapi, daemon=True)
        self.thread_connect_dms.start()

        signal.signal(signal.SIGINT, self.signal_handler)
        while not self.exit_event.is_set():
            time.sleep(0.5)
        self.logger.info("Program terminated.")


def main():
    try:
        fake_dms = FakeDms()
        fake_dms.run()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
