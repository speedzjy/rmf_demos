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

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import qos_profile_system_default
from rclpy.qos import QoSProfile
from rclpy.qos import QoSHistoryPolicy as History
from rclpy.qos import QoSDurabilityPolicy as Durability
from rclpy.qos import QoSReliabilityPolicy as Reliability

from std_msgs.msg import String

from rmf_task_msgs.msg import ApiRequest, ApiResponse


###############################################################################


class TaskCommunicator(Node):

    def __init__(self, argv=sys.argv):
        super().__init__("task_communicator")

        # flask后端
        self.app = Flask(__name__)
        self.setup_routes()

        self.request_id_lock = threading.Lock()
        self.request_responses = defaultdict()

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-o",
            "--orientation",
            required=False,
            type=float,
            help="Orientation to face in degrees (optional)",
        )
        parser.add_argument(
            "--use_sim_time", action="store_true", help="Use sim time, default: false"
        )

        self.args = parser.parse_args(argv[1:])

        transient_qos = QoSProfile(
            history=History.KEEP_LAST,
            depth=1,
            reliability=Reliability.RELIABLE,
            durability=Durability.TRANSIENT_LOCAL,
        )

        self.pub_req = self.create_publisher(
            ApiRequest, "task_api_requests", transient_qos
        )

        # enable ros sim time
        if self.args.use_sim_time:
            self.get_logger().info("Using Sim Time")
            param = Parameter("use_sim_time", Parameter.Type.BOOL, True)
            self.set_parameters([param])

        self.sub_res = self.create_subscription(
            ApiResponse, "task_api_responses", self.receive_response, 10
        )

        self.async_loop = asyncio.new_event_loop()

        self.run()

    def receive_response(self, response_msg: ApiResponse):
        with self.request_id_lock:
            if response_msg.request_id not in self.request_responses:
                self.request_responses.update(
                    {response_msg.request_id: response_msg.json_msg}
                )

    def setup_routes(self):
        @self.app.route("/assign", methods=["POST"])
        def assign():
            data = request.get_json()
            destination = data.get("destination")
            robot = data.get("robot")
            fleet = data.get("fleet")
            dms_cmd_id = data.get("dms_cmd_id", 0)

            if destination is None or robot is None or fleet is None:
                return (
                    jsonify(
                        {"error": "Missing key 'destination' or 'robot' or 'fleet'"}
                    ),
                    400,
                )

            self.get_logger().info(f"\033[92mReceived assignment\033[0m: {data}")

            self.async_loop.create_task(
                self.task_tracker(dms_cmd_id, robot, fleet, destination)
            )

            return jsonify(
                {
                    "status": "success",
                    "destination": destination,
                    "robot": robot,
                    "fleet": fleet,
                    "dms_cmd_id": dms_cmd_id,
                }
            )

    async def task_tracker(self, dms_cmd_id, robot, fleet, destination):
        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] task \033[92mbegin\033[0m"
        )

        # 等待看是否有停车任务
        self.get_logger().info(f"[async \033[92m{robot}\033[0m] Check parking task...")
        await asyncio.sleep(1.0)
        parking_task_id = await self.get_robot_task_id(robot, fleet)
        if bool(parking_task_id):
            self.get_logger().info(
                f"[async \033[92m{robot}\033[0m] parking task id: {parking_task_id}"
            )
            await self.cancel_task(robot, parking_task_id)
        else:
            self.get_logger().info(
                f"[async \033[92m{robot}\033[0m] parking task not found, no need to cancel"
            )

        request_id = await self.go_to_place(robot, fleet, destination)

        await self.wait_for_task_completion_async(request_id, robot)

        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] task \033[92mend\033[0m"
        )

        await asyncio.sleep(1.0)
        await self.go_to_place(robot, fleet, f"{robot}_charger")

    async def cancel_task(self, robot, task_id):
        self.get_logger().info(f"[async \033[92m{robot}\033[0m] Cancel task: {task_id}")

        response = asyncio.Future()

        msg = ApiRequest()
        msg.request_id = "cancel_task_" + str(uuid.uuid4())
        payload = {}
        payload["type"] = "cancel_task_request"
        payload["task_id"] = task_id

        msg.json_msg = json.dumps(payload)
        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] cancel task msg: \n{json.dumps(payload, indent=2)}"
        )
        self.pub_req.publish(msg)

        while not response.done():
            with self.request_id_lock:
                if msg.request_id in self.request_responses:
                    response.set_result(
                        json.loads(self.request_responses[msg.request_id])
                    )
                    self.request_responses.pop(msg.request_id)
                    self.get_logger().info(
                        f"[async \033[92m{robot}\033[0m] Got response:\n{response.result()}"
                    )
                    break
            await asyncio.sleep(0.3)

        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] Cancel task \033[92mreceived\033[0m"
        )

    async def get_robot_task_id(self, robot, fleet):
        url = f"http://localhost:8000/fleets/{fleet}/state"

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            parking_task_id = parking_task_id = (
                                data.get("robots", None)
                                .get(robot, None)
                                .get("task_id", "")
                            )

                            break
                        else:
                            self.get_logger().info(
                                f"[async \033[92m{robot}\033[0m] Got unexpected status code \033[91m{response.status}\033[0m, retrying..."
                            )
                except aiohttp.ClientConnectorError:
                    self.get_logger().info(
                        "[async \033[92m{robot}\033[0m] Connection error (endpoint not ready yet), retrying..."
                    )

                await asyncio.sleep(1.0)

        return parking_task_id

    async def go_to_place(self, robot, fleet, destination, orientation=0):
        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] Send task: \033[92m{robot}\033[0m go to \033[92m{destination}\033[0m"
        )
        response = asyncio.Future()

        msg = ApiRequest()
        msg.request_id = "direct_" + str(uuid.uuid4())

        payload = {}
        payload["type"] = "robot_task_request"
        payload["robot"] = robot
        payload["fleet"] = fleet

        # Define task request description
        go_to_activity = {
            "category": "go_to_place",
            "description": {
                "waypoint": destination,
                "orientation": orientation * math.pi / 180.0,
            },
        }

        rmf_task_request = {
            "category": "compose",
            "description": {
                "category": "go_to_place",
                "phases": [{"activity": go_to_activity}],
            },
            "unix_millis_earliest_start_time": 0,
        }

        payload["request"] = rmf_task_request

        msg.json_msg = json.dumps(payload)

        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] Json msg payload: \n{json.dumps(payload, indent=2)}"
        )

        self.pub_req.publish(msg)

        while not response.done():
            with self.request_id_lock:
                if msg.request_id in self.request_responses:
                    response.set_result(
                        json.loads(self.request_responses[msg.request_id])
                    )
                    self.request_responses.pop(msg.request_id)
                    self.get_logger().info(
                        f"[async \033[92m{robot}\033[0m] Got response:\n{response.result()}"
                    )
                    break
            await asyncio.sleep(0.3)

        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] Send task: \033[92m{robot}\033[0m go to \033[92m{destination} \033[92mreceived\033[0m"
        )

        return msg.request_id

    async def wait_for_task_completion_async(
        self, request_id, robot, poll_interval=1.0
    ):
        url = f"http://localhost:8000/tasks/{request_id}/state"
        self.get_logger().info(
            f"[async \033[92m{robot}\033[0m] Waiting for task {request_id} to complete..."
        )

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            status = data.get("status")

                            if status == "completed":
                                self.get_logger().info(
                                    f"[async \033[92m{robot}\033[0m] Task {request_id} is completed."
                                )
                                break
                        else:
                            self.get_logger().info(
                                f"[async \033[92m{robot}\033[0m] Got unexpected status code \033[91m{response.status}\033[0m, retrying..."
                            )
                except aiohttp.ClientConnectorError:
                    self.get_logger().info(
                        "[async \033[92m{robot}\033[0m] Connection error (endpoint not ready yet), retrying..."
                    )

                await asyncio.sleep(poll_interval)

    def tracker_loop(self):
        asyncio.set_event_loop(self.async_loop)

        async def check_exit_event():
            while rclpy.ok():
                await asyncio.sleep(1)
            self.async_loop.stop()

        self.async_loop.create_task(check_exit_event())
        self.async_loop.run_forever()

    def run_flask(self, port=6001):
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.CRITICAL)
        print(f"\n\033[92m * Flask app is starting on port: {port}\033[0m")
        self.app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)

    def run(self):
        self.thread_async_loop = threading.Thread(target=self.tracker_loop)
        self.thread_async_loop.start()

        self.thread_connect_dms = threading.Thread(target=self.run_flask, daemon=True)
        self.thread_connect_dms.start()


###############################################################################


def main(argv=sys.argv):
    rclpy.init(args=sys.argv)
    args_without_ros = rclpy.utilities.remove_ros_args(sys.argv)

    task_requester = TaskCommunicator(args_without_ros)

    executor = MultiThreadedExecutor()
    executor.add_node(task_requester)
    executor.spin()

    rclpy.shutdown()


if __name__ == "__main__":
    main(argv=sys.argv)
