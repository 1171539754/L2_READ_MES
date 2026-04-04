from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
import time
from datetime import datetime
# 定时读取mes任务，需要开发炉次信息、

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

BASE_URL = "http://127.0.0.1:5001"

def task_get_status():
    """任务1：每隔10秒GET一次状态"""
    try:
        resp = requests.get(f"{BASE_URL}/HTTP/heat_end", timeout=5)
        resp.raise_for_status()
        logging.info(f"[GET] 状态数据: {resp.json()}")

    except Exception as e:
        logging.error(f"[GET] 失败: {e}")

def task_report_data():
    """任务2：每隔30秒POST一次数据"""
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "value": 123
        }
        resp = requests.post(f"{BASE_URL}/report", json=data, timeout=5)
        resp.raise_for_status()
        logging.info(f"[POST] 上报成功: {resp.json()}")
    except Exception as e:
        logging.error(f"[POST] 失败: {e}")

# 创建后台调度器（非阻塞，会在后台线程池中运行）
scheduler = BackgroundScheduler()

# 添加多个任务，分别设定间隔
scheduler.add_job(task_get_status, 'interval', seconds=10, id='get_status')
scheduler.add_job(task_report_data, 'interval', seconds=30, id='report_data')

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