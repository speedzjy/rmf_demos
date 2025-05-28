import threading
import time
import requests

from datetime import datetime, timedelta
from pydantic import BaseModel


class Task(BaseModel):
    name: str
    stamp: str
    expr_no: str
    vials_count: int
    steps: list
    level: int  # 无效参数
