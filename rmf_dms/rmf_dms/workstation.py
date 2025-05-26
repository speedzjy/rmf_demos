import threading
import time
import requests
import os
import json

from datetime import datetime, timedelta
from pydantic import BaseModel


class WorkstationStatusUpdate(BaseModel):
    workstationType: str
    name: str
    code: str
    status: str
    capacity: int
    machineList: list
    sectionList: list = []
    remark: str = ""


class Workstation:
    def __init__(
        self,
        workstation_type: str,
        name: str,
        code: str,
        capacity: int = 10,
        heartbeat_url: str = "http://localhost:6060/heartbeat",
        heartbeat_interval: float = 3,
        task_finish_url: str = "http://localhost:6060/finish_signal",
        event: threading.Event = None,
        logger=None,
    ):
        self.workstation_type = workstation_type
        self.name = name
        self.code = code
        self.capacity = capacity

        if "dispensing" in self.code:
            liquid_channel = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "ws_channel_info",
                "liquid_channel.json",
            )
            solid_channel = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "ws_channel_info",
                "solid_channel.json",
            )

            if "liquid" in self.code:
                with open(liquid_channel, "r") as f:
                    channel_list = json.load(f)
            elif "solid" in self.code:
                with open(solid_channel, "r") as f:
                    channel_list = json.load(f)
            else:
                channel_list = []
            self.machine_list = [
                {"machineTypeCode": self.workstation_type, "channelList": channel_list}
            ]
        else:
            self.machine_list = [
                {
                    "machineTypeCode": self.workstation_type,
                }
            ]

        self.section_list = [{"sectionCode": "lab", "sectionName": "lab"}]

        self._records_lock = threading.Lock()
        self._task_records = {}

        self.heartbeat_url = heartbeat_url
        self.heartbeat_interval = heartbeat_interval
        self.task_finish_url = task_finish_url
        self.exit_event = event if event else threading.Event()
        self.logger = logger

        self.thread_heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread_heartbeat.start()

        self.thread_monitor = threading.Thread(target=self._monitor_tasks, daemon=True)
        self.thread_monitor.start()

    def start(self, one_assign: dict, default_duration: float = 1.0):
        """
        启动任务并记录任务开始时间与持续时间。
        """
        with self._records_lock:
            self._task_records = {
                "start": datetime.now(),
                "duration": (
                    one_assign["time"]
                    if one_assign["time"] is not None
                    else default_duration
                ),
                "status": "processing",
                "assign": one_assign,
            }

    @property
    def status(self) -> str:
        """
        动态计算工作站状态：若有未完成任务则为 BUSY, 否则为 IDLE。
        """
        return "BUSY" if self._task_records else "IDLE"

    def _monitor_tasks(self):
        """
        后台线程，定期检查任务是否已完成。
        """
        while not self.exit_event.is_set():
            now = datetime.now()
            with self._records_lock:
                if self._task_records:
                    # 以分钟为单位计算已用时间
                    # elapsed = (now - self._task_records["start"]).total_seconds() # 以s为单位，测试用
                    elapsed = (now - self._task_records["start"]).total_seconds() / 60.0
                    if elapsed >= self._task_records["duration"]:
                        self._task_records["status"] = "finish"

                        try:
                            response = requests.post(
                                self.task_finish_url,
                                json=self._task_records["assign"],
                                headers={"Content-Type": "application/json"},
                            )
                            if response.status_code == 200:
                                self.logger.info(
                                    f"{self.code} 发送任务完成指令成功"
                                )
                                # 发送成功后清空任务记录
                                self._task_records = {}
                            else:
                                # 如果状态码不是200，记录错误信息
                                self.logger.error(
                                    f"{self.code} 发送任务完成指令失败: {response.status_code} - {response.text}"
                                )
                        except requests.RequestException as e:
                            self.logger.error(
                                f"{self.code} 发送任务完成指令请求失败: {e}"
                            )

            time.sleep(0.2)

    def _heartbeat(self):
        while not self.exit_event.is_set():
            time.sleep(self.heartbeat_interval)

            # self.logger.info(f"Heartbeat from {self.code}: {self.status}")

            data = WorkstationStatusUpdate(
                workstationType=self.workstation_type,
                name=self.name,
                code=self.code,
                status=self.status,
                capacity=self.capacity,
                machineList=self.machine_list,
                sectionList=self.section_list,
                remark="",
            ).dict()

            try:
                response = requests.post(self.heartbeat_url, json=data, timeout=2.0)
                if response.status_code != 200:
                    self.logger.warning(
                        f"Failed to send heartbeat: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
