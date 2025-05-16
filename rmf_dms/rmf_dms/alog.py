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

import logging
import time
import os
import rospkg
import re
import colorama
from colorama import Fore, Style
from logging.handlers import TimedRotatingFileHandler

colorama.init()


class AsyncLog(object):
    def __init__(self, logger=None, file_name=None):
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.INFO)
        self.log_time = time.strftime("%Y_%m_%d")

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # 定义handler的输出格式
        formatter = logging.Formatter(
            "[%(asctime)s] %(filename)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        ch.setFormatter(formatter)

        self.logger.addHandler(ch)
        ch.close()

    def info(self, message):
        self.logger.info(message)

    def info_green(self, message):
        self.logger.info(Fore.GREEN + message + Style.RESET_ALL)

    def info_green_bright(self, message):
        self.logger.info(Fore.GREEN + Style.BRIGHT + message + Style.RESET_ALL)

    def info_yellow_bright(self, message):
        self.logger.info(Fore.YELLOW + Style.BRIGHT + message + Style.RESET_ALL)

    def info_red_bright(self, message):
        self.logger.info(Fore.RED + Style.BRIGHT + message + Style.RESET_ALL)
