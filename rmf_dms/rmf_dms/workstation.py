import threading
import time
import requests

from datetime import datetime, timedelta
from pydantic import BaseModel


class WorkstationStatusUpdate(BaseModel):
    workstationType: str
    name: str
    code: str
    status: str
    capacity: int


class Workstation:
    def __init__(
        self,
        workstation_type: str,
        name: str,
        code: str,
        capacity: int = 10,
        heartbeat_url: str = "http://localhost:6060/heartbeat",
        heartbeat_interval: float = 3,
        event: threading.Event = None,
        logger=None,
    ):
        self.workstation_type = workstation_type
        self.name = name
        self.code = code
        self.capacity = capacity
        self._task_records = (
            {}
        )  #  dms_cmd_id: {"start": datetime, "duration": float, "status": "procerssing"/"finish"}
        self._unfinished_tasks = set()

        self.heartbeat_url = heartbeat_url
        self.heartbeat_interval = heartbeat_interval
        self.exit_event = event if event else threading.Event()
        self.logger = logger

        self.thread_heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread_heartbeat.start()

        self.thread_monitor = threading.Thread(target=self._monitor_tasks, daemon=True)
        self.thread_monitor.start()

    def start(self, dms_cmd_id: str, duration: float):
        """
        启动任务并记录任务开始时间与持续时间。
        """
        self._task_records[dms_cmd_id] = {
            "start": datetime.now(),
            "duration": duration,
            "status": "processing",
        }

    @property
    def status(self) -> str:
        """
        动态计算工作站状态：若有未完成任务则为 BUSY, 否则为 IDLE。
        """
        if all(record["status"] == "finish" for record in self._task_records.values()):
            return "IDLE"
        return "BUSY"

    def _monitor_tasks(self):
        """
        后台线程，定期检查任务是否已完成。
        """
        while not self.exit_event.is_set():
            now = datetime.now()
            for dms_cmd_id, record in self._task_records.items():
                if record["status"] != "finish":
                    elapsed = (now - record["start"]).total_seconds()
                    if elapsed >= record["duration"]:
                        record["status"] = "finish"
            time.sleep(0.5)

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
            ).dict()

            try:
                response = requests.post(self.heartbeat_url, json=data, timeout=2.0)
                if response.status_code != 200:
                    self.logger.warning(
                        f"Failed to send heartbeat: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
