from .Workstation import Workstation

class FakeDms:
    def __init__(self):
        pass

def main():
    # 示例用法
    ws = Workstation("WS1", 2)
    ws.start("cmd1", 5)  # 启动任务 cmd1，持续时间 5 秒
    print(ws.status)  # 输出：BUSY

    import time

    for i in range(6):
        time.sleep(1)
        print(ws.is_finish("cmd1"))  # 输出：True
        print(ws.status)  # 输出：IDLE

    # 添加瓶子
    ws.add_bottles("BottleA")
    ws.add_bottles(["BottleB", "BottleC"])
    print(ws.get_bottle_list())  # ['BottleA', 'BottleB', 'BottleC']

    # 移除瓶子
    ws.remove_bottles("BottleA")
    ws.remove_bottles(["BottleX", "BottleB"])  # BottleX 不存在，不报错
    print(ws.get_bottle_list())  # ['BottleC']



if __name__ == "__main__":
    main()
