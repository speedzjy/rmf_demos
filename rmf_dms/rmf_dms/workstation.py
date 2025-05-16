from datetime import datetime, timedelta


class Workstation:
    def __init__(self, name: str, capacity: int, bottle_set: set = set()):
        self.name = name
        self.capacity = capacity
        self._task_records = {}  # dms_cmd_id: (start_time, duration)
        self._unfinished_tasks = set()
        self.bottle_set = bottle_set

    def start(self, dms_cmd_id: str, duration: float):
        """
        启动任务并记录任务开始时间与持续时间。
        """
        self._task_records[dms_cmd_id] = (datetime.now(), duration)
        self._unfinished_tasks.add(dms_cmd_id)

    def is_finish(self, dms_cmd_id: str) -> bool:
        """
        检查某任务是否完成。
        """
        if dms_cmd_id not in self._task_records:
            return False
        start_time, duration = self._task_records[dms_cmd_id]
        finished = datetime.now() - start_time >= timedelta(seconds=duration)
        if finished:
            self._unfinished_tasks.discard(dms_cmd_id)  # 只在完成时移除
        return finished

    @property
    def status(self) -> str:
        """
        动态计算工作站状态：若有未完成任务则为 BUSY, 否则为 IDLE。
        """
        now = datetime.now()
        # 检查未完成集合中是否还有未过期的任务
        to_remove = []
        for dms_cmd_id in self._unfinished_tasks:
            start_time, duration = self._task_records[dms_cmd_id]
            if now - start_time < timedelta(seconds=duration):
                return "BUSY"
            else:
                to_remove.append(dms_cmd_id)
        # 清理已完成的任务（延迟清除）
        for dms_cmd_id in to_remove:
            self._unfinished_tasks.discard(dms_cmd_id)
        return "IDLE"

    def add_bottles(self, bottles):
        if isinstance(bottles, list):
            self.bottle_set.update(bottles)
        else:
            self.bottle_set.add(bottles)

    def remove_bottles(self, bottles):
        if not isinstance(bottles, list):
            bottles = [bottles]
        self.bottle_set.difference_update(bottles)  # 批量移除更快

    def get_bottle_list(self):
        return list(self.bottle_set)  # 如果你还需要展示为列表
