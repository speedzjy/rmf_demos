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

import os
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
import sqlite3

from fastapi import FastAPI, File, UploadFile


from flask import Flask, request, make_response, jsonify
from collections import defaultdict

from .alog import AsyncLog
from .workstation import WorkstationStatusUpdate, Workstation

database_file = "dms.db"


class FakeDms:
    def __init__(self):
        # --------------------日志设置-----------------------------
        self.logger = AsyncLog(self.__class__.__name__)
        # -------------------------------------------------------

        # --------------------数据库设置--------------------------
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_name = os.path.join(script_dir, database_file)
        self.init_db()
        # -------------------------------------------------------

        # --------------------FastAPI后端--------------------------
        self.app = FastAPI()
        self.setup_routes()
        # ---------------------------------------------------------

        # ----------------------临时内存数据-------------------------
        self.workstation_status = defaultdict(
            WorkstationStatusUpdate
        )  # 包括工作站和机器人

        # 只包括工作站
        self.ws_instance_dict = defaultdict(Workstation)
        # ----------------------------------------------------------

        self.exit_event = threading.Event()

    def init_db(self):
        """初始化数据库，创建表（如果不存在）"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workstation_tb (
                    workstationType TEXT NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL PRIMARY KEY,
                    status TEXT NOT NULL,
                    capacity INTEGER NOT NULL DEFAULT 10
                )
            """
            )
            conn.commit()
            self.logger.info(f"Database '{self.db_name}' initialized.")
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database: {e}")
        finally:
            if conn:
                conn.close()

    def setup_routes(self):
        @self.app.get("/")
        async def hello():
            return "Hello, World!"

        @self.app.post("/heartbeat")
        async def heartbeat(ws_status: WorkstationStatusUpdate):
            self.workstation_status[ws_status.code] = ws_status
            return {"status": "ok", "message": f"Status for {ws_status.code} updated."}

    def run_fastapi(self, port=6060):
        print(f"\n\033[92mStart: FastAPI app is starting on port: {port}\033[\n")
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            # log_level="warning",
            debug=True,
        )

    def run_update_db(self):
        while not self.exit_event.is_set():
            # --- 执行数据库更新逻辑 ---
            conn = None
            try:
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()

                # 为了安全地遍历字典（防止在遍历时被 heartbeart 并发修改导致 RuntimeError），复制一份字典的值来进行迭代。
                ws_status_to_update = list(self.workstation_status.values())

                # 只有当字典中有数据时才进行更新
                if ws_status_to_update:
                    # SQL 语句：如果 code 存在则替换整行，否则插入
                    sql = """
                        INSERT OR REPLACE INTO workstation_tb (workstationType, name, code, status, capacity)
                        VALUES (?, ?, ?, ?, ?)
                    """

                    data_to_insert = []
                    for ws_status in ws_status_to_update:
                        try:
                            data_to_insert.append(
                                (
                                    ws_status.workstationType,
                                    ws_status.name,
                                    ws_status.code,
                                    ws_status.status,
                                    ws_status.capacity,
                                )
                            )
                        except Exception as e:
                            self.logger.error(f"Error insert for {ws_status.code}: {e}")
                            continue  # 跳过当前循环，处理下一条数据

                    if data_to_insert:
                        # 使用 executemany 批量执行插入/更新，效率更高
                        cursor.executemany(sql, data_to_insert)
                        conn.commit()
                        # 记录更新成功的日志，可以使用 debug 级别避免日志过多
                        self.logger.debug(
                            f"Inserted/replaced {len(data_to_insert)} workstation statuses."
                        )
                    else:
                        self.logger.debug("No valid workstation statuses to update.")

            except sqlite3.Error as e:
                self.logger.error(f"Error updating database: {e}")
            except Exception as e:
                # 捕获其他可能的异常
                self.logger.error(f"An unexpected error occurred during DB update: {e}")
            finally:
                # 确保在每个更新周期后关闭数据库连接
                if conn:
                    conn.close()

            time.sleep(1.0)

    def run_fake_ws(self):
        ws_code_list = ["liquid_1", "solid_1", "powder_1"]
        for ws_code in ws_code_list:
            ws = Workstation(
                workstation_type=ws_code.split("_")[0],
                name=ws_code,
                code=ws_code,
                event=self.exit_event,
                logger=self.logger,
            )
            self.ws_instance_dict[ws_code] = ws
        # 模拟工作站状态更新
        while not self.exit_event.is_set():
            self.exit_event.wait(3.0)

    def run_fake_robot(self):
        pass

    def run(self):
        self.thread_connect_dms = threading.Thread(target=self.run_fastapi, daemon=True)
        self.thread_connect_dms.start()

        self.thread_update_db = threading.Thread(target=self.run_update_db)
        self.thread_update_db.start()

        self.thread_fake_ws = threading.Thread(target=self.run_fake_ws)
        self.thread_fake_ws.start()

        self.thread_fake_robot = threading.Thread(target=self.run_fake_robot)
        self.thread_fake_robot.start()

        def _signal_handler(sig, frame):
            print("\n")
            self.exit_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
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
