import sqlite3
import logging
import json
import uuid
import datetime


class DBHandler:
    def __init__(self, db_name, logger: logging.Logger):
        self.db_name = db_name
        self.logger = logger
        # Connect to the SQLite database.
        self.connection = sqlite3.connect(self.db_name)
        self.connection.row_factory = sqlite3.Row

    def init_db(self):
        """初始化数据库，创建表（如果不存在）"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workstation_tb (
                    workstationType TEXT NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL PRIMARY KEY,
                    status TEXT NOT NULL,
                    capacity INTEGER NOT NULL DEFAULT 10,
                    machineList TEXT NOT NULL,
                    sectionList TEXT NOT NULL,
                    remark TEXT
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bottle_location_tb (
                    bottleCode TEXT NOT NULL PRIMARY KEY,
                    location TEXT NOT NULL,
                    is_used BOOLEAN NOT NULL DEFAULT 0,
                    lastUpdated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bottle_record_tb (
                    createdTime DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updatedTime DATETIME DEFAULT CURRENT_TIMESTAMP,
                    stepId TEXT NOT NULL,
                    "index" INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workstation TEXT NOT NULL,
                    workstationType TEXT NOT NULL,
                    finishTime TEXT,
                    time INTEGER,
                    scheduleId TEXT NOT NULL,
                    robot TEXT NOT NULL,
                    expr_no TEXT NOT NULL,
                    fjspb_index INTEGER NOT NULL,
                    bottle_code TEXT NOT NULL,
                    PRIMARY KEY (expr_no, fjspb_index, bottle_code, workstation, robot, operation)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS task_tb (
                    name TEXT NOT NULL,
                    expr_no TEXT NOT NULL PRIMARY KEY,
                    stamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    vials_count INTEGER NOT NULL,
                    steps TEXT NOT NULL,
                    length INTEGER NOT NULL,
                    finished BOOLEAN NOT NULL DEFAULT 0
                )
                """
            )

            self.connection.commit()
            self.logger.info(f"Database '{self.db_name}' initialized.")
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database: {e}")

    def init_bottle_tb(self, num_bottles=20):
        cursor = self.connection.cursor()

        # 检查表是否为空
        cursor.execute("SELECT COUNT(*) FROM bottle_location_tb")
        count = cursor.fetchone()[0]

        if count == 0:
            bottles = [
                ("bottle-" + str(i), "starting_station")
                for i in range(1, num_bottles + 1)
            ]
            cursor.executemany(
                "INSERT INTO bottle_location_tb (bottleCode, location) VALUES (?, ?)",
                bottles,
            )
            self.logger.info("bottle_tb 插入初始瓶子记录。")
        else:
            self.logger.info("bottle_tb 已包含数据, 跳过初始化。")

        self.connection.commit()

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()

    def fetch_bottle_list(self, ws_code):
        """
        Fetch all bottles from the database for a given workstation code.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM bottle_location_tb WHERE location = ?", (ws_code,)
        )
        return [{"bottleCode": row["bottleCode"]} for row in cursor.fetchall()]

    def fetch_ws_info(self):
        """
        Fetch all workstation information from the database.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM workstation_tb")
        rows = cursor.fetchall()

        workstation_list = []
        for row in rows:
            workstation_info = {
                "workstationType": row["workstationType"],
                "name": row["name"],
                "code": row["code"],
                "status": row["status"],
                "bottleSlotCount": row["capacity"],
                "bottleList": self.fetch_bottle_list(row["code"]),
                "machineList": json.loads(row["machineList"]),
                "sectionList": json.loads(row["sectionList"]),
                "remark": row["remark"],
            }
            workstation_list.append(workstation_info)

        return workstation_list

    def fetch_robot_info(self):
        """
        Fetch all workstation information from the database.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM workstation_tb WHERE workstationType = 'robot'")
        rows = cursor.fetchall()

        robot_list = []
        for row in rows:
            robot_info = {
                "workstationType": row["workstationType"],
                "name": row["name"],
                "code": row["code"],
                "status": row["status"],
                "bottleSlotCount": row["capacity"],
                "bottleList": self.fetch_bottle_list(row["code"]),
            }
            robot_list.append(robot_info)

        return robot_list

    def fetch_task_info(self):
        """
        Fetch all task information from the database.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM task_tb WHERE finished = 0")
        rows = cursor.fetchall()

        task_list = []
        for row in rows:
            task_info = {
                "name": row["name"],
                "expr_no": row["expr_no"],
                "stamp": row["stamp"],
                "vials_count": row["vials_count"],
                "steps": json.loads(row["steps"]),
            }
            task_list.append(task_info)

        return task_list

    def fetch_bottle_record_info(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM bottle_record_tb")
        rows = cursor.fetchall()
        bottle_record_list = []
        for row in rows:
            bottle_record_info = {
                "createdTime": row["createdTime"],
                "updatedTime": row["updatedTime"],
                "stepId": row["stepId"],
                "index": row["index"],
                "operation": row["operation"],
                "status": row["status"],
                "workstation": row["workstation"],
                "workstationType": row["workstationType"],
                "finishTime": row["finishTime"],
                "time": row["time"],
                "scheduleId": row["scheduleId"],
                "robot": row["robot"],
                "expr_no": row["expr_no"],
                "fjspb_index": row["fjspb_index"],
                "bottle_code": row["bottle_code"],
            }
            bottle_record_list.append(bottle_record_info)
        return bottle_record_list

    def allocate_bottles(self, vials_count: int):
        cursor = self.connection.cursor()

        # 查询未使用的瓶子，按 bottleCode 排序，限制数量为 vials_count
        cursor.execute(
            """
            SELECT bottleCode FROM bottle_location_tb
            WHERE is_used = 0
            LIMIT ?
            """,
            (vials_count,),
        )
        bottles = [row[0] for row in cursor.fetchall()]

        if not bottles or len(bottles) < vials_count:
            raise ValueError("可用瓶子数量不足")

        # 标记这些瓶子为已使用
        cursor.executemany(
            """
            UPDATE bottle_location_tb
            SET is_used = 1,
                lastUpdated = CURRENT_TIMESTAMP
            WHERE bottleCode = ?
            """,
            [(bottle,) for bottle in bottles],
        )

        self.connection.commit()
        return bottles

    def bottle_cleanup(self):
        cursor = self.connection.cursor()

        # 将所有瓶子标记为未使用
        cursor.execute(
            """
            UPDATE bottle_location_tb
            SET is_used = 0,
                lastUpdated = CURRENT_TIMESTAMP
            """
        )

        self.connection.commit()

    def create_assign_if_not_exist(self, one_assign):
        cursor = self.connection.cursor()

        # 根据 workstation code 获取 workstationType
        cursor.execute(
            "SELECT workstationType FROM workstation_tb WHERE code = ?",
            (one_assign["workstation"],),
        )
        result = cursor.fetchone()
        workstation_type = result[0] if result else None  # 如果找不到，设为 None

        cursor.executemany(
            """
            INSERT OR IGNORE INTO bottle_record_tb (
                stepId, "index", operation, status, workstation, workstationType,
                finishTime, time, scheduleId, robot, expr_no, fjspb_index, bottle_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    bottle["stepId"],
                    bottle["index"],
                    one_assign["operation"],
                    "processing",
                    one_assign["workstation"],
                    workstation_type,
                    None,
                    one_assign["time"],
                    one_assign["scheduleId"],
                    one_assign["robot"],
                    bottle["expr_no"],
                    bottle["fjspb_index"],
                    bottle["bottleCode"],
                )
                for bottle in one_assign["bottleList"]
            ],
        )

        self.connection.commit()

    # 更改bottle_record_tb中瓶子的状态为完成，并更改bottle_location_tb中瓶子的位置
    def update_task_status(self, one_assign):
        cursor = self.connection.cursor()
        now = datetime.datetime.now()
        iso_now = now.replace(microsecond=0).isoformat()
        ms_now = int(now.timestamp() * 1000)

        cursor.executemany(
            """
            UPDATE bottle_record_tb
            SET status = 'finish', updatedTime = ?, finishTime = ?
            WHERE 
            expr_no = ? AND fjspb_index = ? AND bottle_code = ? 
            AND workstation = ? AND robot = ? AND operation = ?
            """,
            [
                (
                    iso_now,
                    # 适应原化学家1.0的逻辑
                    (
                        str(ms_now)
                        if one_assign["time"] is None
                        else str(ms_now - int(one_assign["time"]) * 60 * 1000)
                    ),
                    bottle["expr_no"],
                    bottle["fjspb_index"],
                    bottle["bottleCode"],
                    one_assign["workstation"],
                    one_assign["robot"],
                    one_assign["operation"],
                )
                for bottle in one_assign["bottleList"]
            ],
        )

        if one_assign["operation"] in ("take", "put"):
            new_location = (
                one_assign["robot"]
                if one_assign["operation"] == "take"
                else one_assign["workstation"]
            )
            cursor.executemany(
                """
                UPDATE bottle_location_tb
                SET location = ?, lastUpdated = CURRENT_TIMESTAMP
                WHERE bottleCode = ?
                """,
                [
                    (new_location, bottle["bottleCode"])
                    for bottle in one_assign["bottleList"]
                ],
            )

        self.connection.commit()

    def execute_finish_assign(self, one_assign):
        """
        完成一个任务分配，更新数据库中的记录。
        """
        cursor = self.connection.cursor()

        # 1. 聚合：找出每个 expr_no 的最大 index
        expr_index_map = {}
        for bottle in one_assign["bottleList"]:
            expr_no = bottle["expr_no"]
            index = bottle["index"]
            if expr_no not in expr_index_map or index > expr_index_map[expr_no]:
                expr_index_map[expr_no] = index

        # 2. 遍历每个 expr_no 检查是否任务已完成
        for expr_no, max_index in expr_index_map.items():
            cursor.execute("SELECT length FROM task_tb WHERE expr_no = ?", (expr_no,))
            result = cursor.fetchone()
            if result and result[0] == max_index:
                # 更新为 finished
                cursor.execute(
                    "UPDATE task_tb SET finished = 1 WHERE expr_no = ?", (expr_no,)
                )

        self.connection.commit()
