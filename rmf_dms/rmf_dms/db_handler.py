import sqlite3
import logging


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
                    capacity INTEGER NOT NULL DEFAULT 10
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
                    id INTEGER PRIMARY KEY,
                    createdTime DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updatedTime DATETIME DEFAULT CURRENT_TIMESTAMP,
                    stepId TEXT NOT NULL,
                    "index" INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workstation TEXT NOT NULL,
                    workstationType TEXT NOT NULL,
                    finishTime DATETIME,
                    time INTEGER,
                    scheduleId TEXT NOT NULL,
                    robot TEXT NOT NULL,
                    expr_no TEXT NOT NULL,
                    fjspb_index INTEGER NOT NULL,
                    bottle_code TEXT NOT NULL
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

    def init_bottle_tb(self):
        cursor = self.connection.cursor()

        # 检查表是否为空
        cursor.execute("SELECT COUNT(*) FROM bottle_location_tb")
        count = cursor.fetchone()[0]

        if count == 0:
            bottles = [("bottle-" + str(i), "starting_station") for i in range(1, 11)]
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
