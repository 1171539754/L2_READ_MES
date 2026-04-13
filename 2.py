from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
import time
from datetime import datetime
import pymongo
from pymongo import UpdateOne

# 数据库连接
db = pymongo.MongoClient("mongodb://localhost:27017/").VOD

# 为 furnace_events 集合创建唯一索引（确保炉号唯一）
furnace_collection = db.furnace_events
furnace_collection.create_index("furnace_id", unique=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

BASE_URL = "http://127.0.0.1:5001"
API_KEY = "LF3"

def fetch_furnace_time_data():
    """
    任务2：从另一个后端获取炉号、起始时间、结束时间，只填充数据库中缺失的字段。
    假设API返回格式：
    {
        "ok": true,
        "data": [
            {"furnace_id": "F001", "start_time": "2025-01-01T08:00:00", "end_time": "2025-01-01T16:00:00"},
            {"furnace_id": "F002", "start_time": "2025-01-02T09:00:00", "end_time": null}
        ]
    }
    如果 end_time 为 null，表示该炉号尚未结束，我们只填充非 null 的时间字段。
    """
    try:
        # 1. 请求外部API（请替换为实际URL）
        dt = datetime.now()
        iso_format = dt.isoformat()
        last_time = f"{iso_format}"

        resp = requests.get(f"{BASE_URL}/{API_KEY}/GetAODEvent",params=last_time, timeout=10)

        resp.raise_for_status()
        result = resp.json()
        if not result.get("ok") or result.get("Ok") is not True:
            logging.warning(f"API返回失败: {result.get('ErrorMsg')}")
            return

        data_list = result.get("data", [])
        if not data_list:
            logging.info("没有获取到炉号数据")
            return

        # 2. 批量查询现有文档，建立 furnace_id -> 文档的映射
        furnace_ids = [item["furnace_id"] for item in data_list]
        existing_docs = {}
        for doc in furnace_collection.find({"furnace_id": {"$in": furnace_ids}}):
            existing_docs[doc["furnace_id"]] = doc

        # 3. 准备批量更新操作
        operations = []
        for item in data_list:
            fid = item["furnace_id"]
            start_time = item.get("start_time")
            end_time = item.get("end_time")

            # 转换时间字符串为 datetime 对象（方便后续查询，也可保留字符串）
            if start_time and isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if end_time and isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)

            # 获取数据库中该炉号的现有文档
            existing = existing_docs.get(fid)
            update_fields = {}

            # 判断是否需要更新起始时间：数据库中没有该字段 或 为 None，且新值不为 None
            if start_time is not None:
                if existing is None or existing.get("start_time") is None:
                    update_fields["start_time"] = start_time

            # 判断是否需要更新结束时间：数据库中没有该字段 或 为 None，且新值不为 None
            if end_time is not None:
                if existing is None or existing.get("end_time") is None:
                    update_fields["end_time"] = end_time

            # 如果没有需要更新的字段，跳过
            if not update_fields:
                continue

            # 构造更新操作（如果文档不存在则插入，同时会带上炉号）
            operations.append(
                UpdateOne(
                    {"furnace_id": fid},
                    {"$set": update_fields},
                    upsert=True
                )
            )

        # 4. 执行批量写入
        if operations:
            result = furnace_collection.bulk_write(operations)
            logging.info(f"炉号数据同步完成: matched={result.matched_count}, upserted={result.upserted_count}, modified={result.modified_count}")
        else:
            logging.info("没有需要更新的炉号时间数据")

    except Exception as e:
        logging.error(f"同步炉号数据失败: {e}")

# ========== 调度器配置 ==========
scheduler = BackgroundScheduler()

scheduler.add_job(fetch_furnace_time_data, 'interval', minutes=30, id='sync_furnace_time')

scheduler.start()

logging.info("定时任务已启动，按 Ctrl+C 退出")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("关闭调度器")
    scheduler.shutdown()