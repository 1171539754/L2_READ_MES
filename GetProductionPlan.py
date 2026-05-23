import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
from datetime import datetime, timedelta
import pymongo
from pymongo import UpdateOne
from pymongo import errors



# 获取生产计划
# 本程序同时用于获取钢种，未开发

#--------- 本接口已完成，未和mes通讯测试  -------------#

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
        self.furnace_collection = self.db.FurnaceEvents

    def fetch_furnace_time_data(self):
        try:
            if not self.is_db_connected():
                logging.info("数据库连接异常")
                return

            # ---------- 改动：从数据库获取最近时间 ----------
            # 查询 Heats.ModifiedAt 最大的文档（即最近同步过的时间）
            last_doc = self.furnace_collection.find_one(
                {"Heats.ModifiedAt": {"$exists": True}},
                sort=[("Heats.ModifiedAt", -1)],
                projection={"Heats.ModifiedAt": 1}
            )
            if last_doc and last_doc.get("Heats", {}).get("ModifiedAt"):
                last_time = last_doc["Heats"]["ModifiedAt"]
                logging.info(f"使用数据库中最新记录时间作为查询起点: {last_time}")
            else:
                # 没有记录时，回退到一天前，避免遗漏
                last_time = (datetime.now().replace(minute=0, second=0, microsecond=0)
                             - timedelta(days=1)).isoformat(sep='T', timespec='seconds')
                logging.info(f"数据库无记录，使用回退时间: {last_time}")
            # ------------------------------------------------

            resp = requests.get(
                f"{self.BASE_URL}/{self.API_KEY}/{self.API}",
                params={"ResultTimeAfter": last_time},
                timeout=30
            )
            resp.raise_for_status()
            result = resp.json()

            if isinstance(result, list):
                result = result[0] if result else {}
            if not result.get("OK"):
                logging.warning(f"API返回失败: {result.get('ErrorMsg')}")
                return

            data_list = result.get(self.data_name, [])
            if isinstance(data_list, dict):
                data_list = [data_list]
            if not data_list:
                logging.info("未找到响应数据")
                return

            # 1. 提取所有 HeatName，查询现有文档
            heat_names = [item["HeatName"] for item in data_list if "HeatName" in item]
            existing_docs = {}
            for doc in self.furnace_collection.find({"HeatName": {"$in": heat_names}}):
                existing_docs[doc["HeatName"]] = doc

            # 2. 生成仅必要的替换操作
            operations = []
            for item in data_list:
                heat_name = item["HeatName"]
                existing = existing_docs.get(heat_name)

                if existing:
                    # 移除 _id 字段再比较（_id 是 MongoDB 自动生成的，API 数据中不会有）
                    existing_clean = {k: v for k, v in existing.items() if k != '_id'}
                    if existing_clean == item:
                        # 内容完全一致，跳过
                        continue

                # 数据有差异，或文档不存在 → 生成 ReplaceOne（upsert=True 保证插入新文档）
                operations.append(
                    UpdateOne(
                        {"HeatName": heat_name},
                        {"$set":
                             {"Heats": item,

                              },
                         },

                        upsert=True
                    )

                )

            if operations:
                result = self.furnace_collection.bulk_write(operations)
                logging.info(
                    f"数据同步完成: matched={result.matched_count}, "
                    f"upserted={result.upserted_count}, modified={result.modified_count}"
                )
            else:
                logging.info("没有需要写入的数据（所有文档均无变化）")

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
    mes_client = MESClient("http://10.10.30.57", "XclMesApi/mes-sendTo-L2-LF3", "GetProductionPlan", "Heats", "HeatName")
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