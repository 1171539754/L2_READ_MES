from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
import time
from datetime import datetime
import pymongo
from datetime import datetime


# 定时读取mes任务，需要开发炉次信息，生产计划
db = pymongo.MongoClient("mongodb://localhost:27017/").VOD

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

BASE_URL = "http://127.0.0.1:5001"
API_KEY = "LF3"

def task_get_GetAODEvent():
    """任务1：每隔60秒GET一次aod冶炼时间"""
    dt = datetime.now()
    iso_format = dt.isoformat()
    # print(iso_format)
    last_time = f"{iso_format}"
    try:
        resp = requests.get(f"{BASE_URL}/LF3/GetAODEvent?SinceTime=\"{last_time}\"", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok") is True:
            if data.get("data") is not None:
                db.sensor_data.insert_one(data)
        logging.info(f"[GET] 状态数据: {resp.json()}")

    except Exception as e:
        logging.error(f"[GET] 失败: {e}")

# 创建后台调度器（非阻塞，会在后台线程池中运行）
scheduler = BackgroundScheduler()

# 添加多个任务，分别设定间隔
scheduler.add_job(task_get_GetAODEvent, 'interval', seconds=10, id='get_status')

# 启动调度器
scheduler.start()

logging.info("定时任务已启动，按 Ctrl+C 退出")

try:
    # 主线程保持运行
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("关闭调度器")
    scheduler.shutdown()

