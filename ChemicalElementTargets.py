import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
from datetime import datetime
import pymongo
from pymongo import UpdateOne, ReplaceOne
from pymongo import errors

#获取钢种信息


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
        self.furnace_collection = self.db.ChemicalElementTargets

    def fetch_furnace_time_data(self):
        try:
            if not self.is_db_connected():
                logging.info("数据库连接异常")
                return

            dt = datetime.now()
            last_time = dt.isoformat()
            resp = requests.get(f"{self.BASE_URL}/{self.API_KEY}/{self.API}",
                                params={"SinceTime": last_time}, timeout=10)
            resp.raise_for_status()
            result = resp.json()

            if isinstance(result, list):
                result = result[0] if result else {}
            if not result.get("Ok"):
                logging.warning(f"API返回失败: {result.get('ErrorMsg')}")
                return

            data_list = result.get(self.data_name, [])
            if isinstance(data_list, dict):
                data_list = [data_list]
            if not data_list:
                logging.info("未找到响应数据")
                return

            operations = []
            for item in data_list:
                # 直接替换整个文档（upsert）
                operations.append(
                    ReplaceOne(
                        {"SteelGradeName": item["SteelGradeName"]},
                        item,
                        upsert=True
                    )
                )

            if operations:
                result = self.furnace_collection.bulk_write(operations)
                logging.info(f"数据同步完成: matched={result.matched_count}, upserted={result.upserted_count}")
            else:
                logging.info("没有需要写入的数据")
        except Exception as e:
            logging.error(f"同步失败: {e}")

    def is_db_connected(self):
        try:
            self.db_URL.admin.command('ping')
            return True
        except (pymongo.errors.ServerSelectionTimeoutError,
                pymongo.errors.ConnectionFailure) as e:
            logging.error(f"数据库连接失败: {e}")
            return False

if __name__ == "__main__":
    mes_client = MESClient("10.10.30.57", "LF3", "GetSteelGrades", "SteelGrades", "SteelGradeName")
    scheduler = BackgroundScheduler()
    scheduler.add_job(mes_client.fetch_furnace_time_data, 'interval', seconds=30, id='sync_furnace_time',max_instances=1,misfire_grace_time=10)
    scheduler.start()
    logging.info("定时任务已启动，按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("关闭调度器")
        scheduler.shutdown()