import requests
import time
import logging
from datetime import datetime

# 配置日志，方便查看运行状态
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 服务器地址（请替换成实际地址）
BASE_URL = "http://127.0.0.1:5001"

def do_get():
    """执行 GET 请求示例"""
    try:
        # 假设获取传感器状态
        response = requests.get(f"{BASE_URL}//HTTP/heat_end", timeout=5)
        response.raise_for_status()  # 如果状态码不是 200，抛出异常
        data = response.json()
        logging.info(f"GET 成功，收到数据: {data}")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"GET 请求失败: {e}")
        return None

def do_post(data_to_send):
    """执行 POST 请求示例，发送数据到服务器"""
    try:
        # 假设上报处理结果
        response = requests.post(f"{BASE_URL}/report", json=data_to_send, timeout=5)
        response.raise_for_status()
        logging.info(f"POST 成功，服务器响应: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"POST 请求失败: {e}")

def job():
    """定时任务：先 GET 数据，处理后再 POST"""
    logging.info("定时任务开始执行")
    # 1. GET 请求获取数据
    received = do_get()
    if received:
        # 2. 对获取的数据做一些处理（这里只是示例，比如加个时间戳）
        processed = {
            "original": received,
            "processed_at": datetime.now().isoformat(),
            "status": "ok"
        }
        # 3. POST 处理后的数据回服务器
        do_post(processed)
    else:
        logging.warning("GET 失败，跳过本次 POST")

def main():
    """主函数，定时循环执行任务"""
    interval_seconds = 30  # 每30秒执行一次
    logging.info(f"启动定时任务，间隔 {interval_seconds} 秒")
    while True:
        job()
        time.sleep(interval_seconds)

if __name__ == "__main__":
    main()