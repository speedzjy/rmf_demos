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
from collections import defaultdict
from pprint import pprint, pformat

from .alog import AsyncLog
from .workstation import WorkstationStatusUpdate, Workstation
from .task import Task
from .db_handler import DBHandler

database_file = "dms.db"


class FakeDms:
    def __init__(self):
        # --------------------日志设置-----------------------------
        self.logger = AsyncLog(self.__class__.__name__)
        # -------------------------------------------------------

        # --------------------数据库设置--------------------------
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_name = os.path.join(script_dir, database_file)

        self.db_handler_main = DBHandler(self.db_name, self.logger)
        self.db_handler_main.init_db()
        self.db_handler_main.init_bottle_tb()
        self.db_handler_main.bottle_cleanup()
        # -------------------------------------------------------

        # --------------------FastAPI后端--------------------------
        self.app = FastAPI()
        self.setup_routes()
        # ---------------------------------------------------------

        # ----------------------临时内存数据-------------------------
        self.task_status = defaultdict(defaultdict)

        self.workstation_status = defaultdict(
            WorkstationStatusUpdate
        )  # 包括工作站和机器人

        # 只包括工作站
        self.ws_instance_dict = defaultdict(Workstation)
        # ----------------------------------------------------------

        self.db_lock = threading.Lock()
        self.task_lock = threading.Lock()
        self.exit_event = threading.Event()

    def setup_routes(self):
        @self.app.post("/heartbeat")
        async def ws_heartbeat(ws_status: WorkstationStatusUpdate):
            self.workstation_status[ws_status.code] = ws_status
            return {"status": "ok", "message": f"Status for {ws_status.code} updated."}

        @self.app.post("/tasks")
        async def tasks(tasks_info: list[Task]):
            with self.task_lock:
                for task in tasks_info:
                    if task.name not in self.task_status:
                        self.task_status[task.name] = {"task": task, "finished": 0}
            return {"status": "ok", "message": "Tasks updated."}

    def run_fastapi(self, port=6060):
        print(f"\n\033[92mStart: FastAPI app is starting on port: {port}\033[0m\n")
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=port,
            # log_level="info",
            log_level="warning",
            debug=True,
        )

    def run_fake_ws(self):
        ws_code_list = [
            {"ws_type": "liquid_dispensing", "ws_code": "liquid_dispensing"},
            {"ws_type": "solid_dispensing", "ws_code": "solid_dispensing"},
            {"ws_type": "magnetic_stirring", "ws_code": "magnetic_stirring"},
            {"ws_type": "starting_station", "ws_code": "starting_station"},
            {"ws_type": "ultrasonic_cleaner", "ws_code": "ultrasonic_cleaner"},
            {"ws_type": "confecting_workstation", "ws_code": "confecting_workstation"},
            {"ws_type": "spotting_workstation", "ws_code": "spotting_workstation"},
            {"ws_type": "furnace_workstation", "ws_code": "furnace_workstation"},
        ]

        for ws_info in ws_code_list:
            ws = Workstation(
                workstation_type=ws_info["ws_type"],
                name=ws_info["ws_code"],
                code=ws_info["ws_code"],
                event=self.exit_event,
                logger=self.logger,
            )
            self.ws_instance_dict[ws_info["ws_code"]] = ws
        # 模拟工作站状态更新
        while not self.exit_event.is_set():
            self.exit_event.wait(3.0)

    def robot_heartbeat(self):
        while not self.exit_event.is_set():
            time.sleep(1.0)

            try:
                response = requests.get("http://localhost:8000/fleets")
                if response.status_code == 200:
                    data = response.json()

                    for fleet in data:
                        for robot_name, robot_info in fleet["robots"].items():
                            robot_status = WorkstationStatusUpdate(
                                workstationType="robot",
                                name=robot_name,
                                code=robot_name,
                                status=robot_info["status"].upper(),
                                capacity=80,
                                machineList=[
                                    {
                                        "machineTypeCode": "robot",
                                    }
                                ],
                                sectionList=[
                                    {"sectionCode": "lab", "sectionName": "lab"}
                                ],
                                remark="",
                            )
                            self.workstation_status[robot_name] = robot_status
                else:
                    self.logger.info(
                        f"GET /fleet failed with status code {response.status_code}"
                    )
            except requests.RequestException as e:
                self.logger.info(f"Error during GET /fleet: {e}")

    def run_update_db(self):
        db_handler_updater = DBHandler(self.db_name, self.logger)

        while not self.exit_event.is_set():
            # --- 执行数据库更新逻辑 ---
            conn = None
            with self.db_lock:
                try:
                    conn = sqlite3.connect(self.db_name)
                    cursor = conn.cursor()

                    # --------------------------------update ws-------------------------------------------------
                    # 为了安全地遍历字典，复制一份字典的值来进行迭代。
                    ws_status_to_update = list(self.workstation_status.values())
                    if ws_status_to_update:
                        cursor.executemany(
                            """
                            INSERT INTO workstation_tb (workstationType, name, code, status, capacity, machineList, sectionList, remark)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(code) DO UPDATE SET
                                status = excluded.status
                            """,
                            [
                                (
                                    ws_status.workstationType,
                                    ws_status.name,
                                    ws_status.code,
                                    ws_status.status,
                                    ws_status.capacity,
                                    json.dumps(ws_status.machineList),
                                    json.dumps(ws_status.sectionList),
                                    ws_status.remark,
                                )
                                for ws_status in ws_status_to_update
                            ],
                        )
                        conn.commit()
                    # --------------------------------------------------------------------------------

                    # --------------------------------update task-----------------------------------
                    with self.task_lock:
                        if list(self.task_status.values()):
                            data_to_insert = []

                            for task_info in self.task_status.values():
                                steps = task_info["task"].steps  # 原地修改

                                if not steps[0]["detail"][0]["actual_no"]:
                                    actual_no_list = (
                                        db_handler_updater.allocate_bottles(
                                            task_info["task"].vials_count
                                        )
                                    )
                                    self.logger.info(
                                        f"Task {task_info['task'].name} 分配瓶子编号: {actual_no_list}"
                                    )

                                    # 对steps中的每个step的detail进行更新
                                    for step in steps:
                                        for i, detail in enumerate(step["detail"]):
                                            if not detail["actual_no"]:
                                                detail["actual_no"] = actual_no_list[i]

                                data_to_insert.append(
                                    (
                                        task_info["task"].name,
                                        task_info["task"].expr_no,
                                        task_info["task"].vials_count,
                                        json.dumps(steps),
                                        len(steps),
                                        int(task_info["finished"]),
                                    )
                                )

                            cursor.executemany(
                                """
                                INSERT INTO task_tb (name, expr_no, vials_count, steps, length, finished)
                                VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT(expr_no) DO UPDATE SET
                                    finished=excluded.finished
                                """,
                                data_to_insert,
                            )
                            conn.commit()
                    # --------------------------------------------------------------------------------

                except sqlite3.Error as e:
                    self.logger.error(f"Error updating database: {e}")
                except Exception as e:
                    # 捕获其他可能的异常
                    self.logger.error(
                        f"An unexpected error occurred during DB update: {e}"
                    )
                finally:
                    # 确保在每个更新周期后关闭数据库连接
                    if conn:
                        conn.close()

            time.sleep(1.0)

        db_handler_updater.close()

    def send_assign(self, one_assign):
        if one_assign["operation"] == "start":
            # 发送指令给工作站
            ws_code = one_assign["workstation"]
            self.ws_instance_dict[ws_code].start(one_assign["bottleList"])
        elif one_assign["operation"] in ["put", "take"]:
            # 发送指令给机器人
            self.robot_execute(
                one_assign["robot"],
                one_assign["operation"],
                one_assign["workstation"],
                one_assign["bottleList"],
            )
            # self.workstation_status[robot_code].put(
            #     one_assign["workstation"],
            #     one_assign["bottleList"],
            #     one_assign["operation"],
            # )
        elif one_assign["operation"] == "finish":
            pass
        else:
            self.logger.info(
                f"Unknown operation: {one_assign['operation']}. Cannot send assign."
            )
    
    def robot_execute(self):
        pass

    def run_scheduler(self):
        self.logger.info("Scheduler is running...")
        db_handler_scheduler = DBHandler(self.db_name, self.logger)

        # 等待到下一个整10秒
        now = time.time()
        next_tick = ((now // 10) + 1) * 10
        time.sleep(next_tick - now)

        while not self.exit_event.is_set():
            start_time = time.time()

            dms_status = {
                "workstation_list": db_handler_scheduler.fetch_ws_info(),
                "bottle_execute_record_list": db_handler_scheduler.fetch_bottle_record_info(),
                "robot_list": db_handler_scheduler.fetch_robot_info(),
                "task_list": db_handler_scheduler.fetch_task_info(),
            }

            # pprint(dms_status)

            next_assign = None
            try:
                response = requests.post(
                    "http://localhost:5050/scheduling",
                    json=dms_status,
                )
                if response.status_code == 200:
                    next_assign = response.json()
                    self.logger.info(f"Scheduler data: {pformat(next_assign)}")
                else:
                    self.logger.info(
                        f"GET /scheduler failed with status code {response.status_code}"
                    )
            except requests.RequestException as e:
                self.logger.info(f"Error during Post /scheduler: {e}")

            if next_assign:
                with self.db_lock:
                    for one_assign in next_assign["data"]:
                        db_handler_scheduler.create_assign_if_not_exist(one_assign)

                # 发指令给机器人和工作站
                for one_assign in next_assign["data"]:
                    self.send_assign(one_assign)

            elapsed_time = time.time() - start_time
            time.sleep(max(0, 10.0 - elapsed_time))

        db_handler_scheduler.close()

    def run(self):
        self.thread_connect_dms = threading.Thread(target=self.run_fastapi, daemon=True)
        self.thread_connect_dms.start()

        self.thread_update_db = threading.Thread(target=self.run_update_db)
        self.thread_update_db.start()

        self.thread_fake_ws = threading.Thread(target=self.run_fake_ws)
        self.thread_fake_ws.start()

        self.thread_fake_robot = threading.Thread(target=self.robot_heartbeat)
        self.thread_fake_robot.start()

        self.thread_scheduler = threading.Thread(target=self.run_scheduler, daemon=True)
        self.thread_scheduler.start()

        def _signal_handler(sig, frame):
            print("\n")
            self.exit_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        while not self.exit_event.is_set():
            time.sleep(0.5)

        self.db_handler_main.close()
        self.logger.info("Program terminated.")


def main():
    try:
        fake_dms = FakeDms()
        fake_dms.run()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
