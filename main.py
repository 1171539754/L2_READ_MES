import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
from datetime import datetime
import pymongo
from pymongo import UpdateOne
from pymongo import errors

# 数据库连接

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
class MESClient:
    def __init__(self,BASE_URL,API_KEY,API,data_name,key):
        # 后端配置
        self.BASE_URL = BASE_URL #后端地址
        self.API_KEY = API_KEY   #后端接口
        self.API = API #后端api

        # 方法用变量
        self.data_name = data_name #类名

        # mongodb配置
        self.key=key
        self.db_URL = pymongo.MongoClient("mongodb://localhost:27017/",connectTimeoutMS=5000,serverSelectionTimeoutMS=5000  )
        self.db = self.db_URL.LF
        self.furnace_collection = self.db.furnace_events

    def fetch_furnace_time_data(self):
        try:
            if not self.is_db_connected():
                logging.info("数据库连接异常")
                return

            dt = datetime.now()
            last_time = dt.isoformat()

            resp = requests.get(
                f"{self.BASE_URL}/{self.API_KEY}/{self.API}",
                params={"SinceTime": last_time},
                timeout=10
            )
            resp.raise_for_status()
            result = resp.json()

            # 处理 result 本身是列表的情况（你的 API 返回的是列表包字典）
            if isinstance(result, list):
                if not result:
                    logging.info("API返回空列表")
                    return
                result = result[0]  # 取第一个元素作为主字典

            # 检查 Ok 字段
            if not result.get("Ok"):
                logging.warning(f"API返回失败: {result.get('ErrorMsg')}")
                return

            # 获取数据（可能是字典或列表）
            data_list = result.get(self.data_name, [])
            if not data_list:
                logging.info("未找到响应数据")
                return

            # 关键修复：如果是字典，转为列表
            if isinstance(data_list, dict):
                data_list = [data_list]
            elif not isinstance(data_list, list):
                logging.warning(f"data_list 类型异常: {type(data_list)}")
                return

            # 提取所有 HeatName
            heat_names = [item["HeatName"] for item in data_list]

            # 查询已存在的文档
            existing_docs = {}
            for doc in self.furnace_collection.find({"HeatName": {"$in": heat_names}}):
                existing_docs[doc["HeatName"]] = doc

            operations = []
            for item in data_list:
                heat_name = item["HeatName"]
                state_code = item.get("StateCode")
                heat_end_time = item.get("HeatEndTime")
                heat_start_time = item.get("HeatStartTime")
                position_code = item.get("PositionCode")

                existing = existing_docs.get(heat_name)
                update_fields = {}

                if heat_start_time is not None:
                    if existing is None or existing.get("HeatStartTime") is None:
                        update_fields["HeatStartTime"] = heat_start_time

                if heat_end_time is not None:
                    if existing is None or existing.get("HeatEndTime") is None:
                        update_fields["HeatEndTime"] = heat_end_time

                if state_code is not None:
                    if existing is None or state_code != existing.get("HeatStateCode"):
                        update_fields["HeatStateCode"] = state_code

                if position_code is not None:
                    if existing is None or position_code != existing.get("PositionCode"):
                        update_fields["PositionCode"] = position_code

                if not update_fields:
                    continue

                operations.append(
                    UpdateOne(
                        {"HeatName": heat_name},
                        {"$set": update_fields},
                        upsert=True
                    )
                )

            if operations:
                result = self.furnace_collection.bulk_write(operations)
                logging.info(
                    f"炉号数据同步完成: matched={result.matched_count}, upserted={result.upserted_count}, modified={result.modified_count}")
            else:
                logging.info("没有需要更新的炉号时间数据")

        except Exception as e:
            logging.error(f"同步炉号数据失败: {e}")

    def is_db_connected(self):
        try:
            self.db_URL.admin.command('ping')
            return True
        except (pymongo.errors.ServerSelectionTimeoutError,
                pymongo.errors.ConnectionFailure) as e:
            logging.error(f"数据库连接失败: {e}")
            return False



if __name__ == "__main__":
    mes_client = MESClient("http://127.0.0.1:5001", "LF3", "GetAODEvent", "VODEvent", "HeatName")
    scheduler = BackgroundScheduler()
    scheduler.add_job(mes_client.fetch_furnace_time_data, 'interval', seconds=5, id='sync_furnace_time')
    scheduler.start()
    logging.info("定时任务已启动，按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("关闭调度器")
        scheduler.shutdown()