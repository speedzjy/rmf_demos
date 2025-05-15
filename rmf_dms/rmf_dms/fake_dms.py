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

from flask import Flask, request, make_response, jsonify
from collections import defaultdict

from .Workstation import Workstation

class FakeDms:
    def __init__(self):
        pass

def main():
    # 示例用法
    ws = Workstation("WS1", 2)
    ws.start("cmd1", 5)  # 启动任务 cmd1，持续时间 5 秒
    print(ws.status)  # 输出：BUSY

    import time

    for i in range(6):
        time.sleep(1)
        print(ws.is_finish("cmd1"))  # 输出：True
        print(ws.status)  # 输出：IDLE

    # 添加瓶子
    ws.add_bottles("BottleA")
    ws.add_bottles(["BottleB", "BottleC"])
    print(ws.get_bottle_list())  # ['BottleA', 'BottleB', 'BottleC']

    # 移除瓶子
    ws.remove_bottles("BottleA")
    ws.remove_bottles(["BottleX", "BottleB"])  # BottleX 不存在，不报错
    print(ws.get_bottle_list())  # ['BottleC']



if __name__ == "__main__":
    main()
