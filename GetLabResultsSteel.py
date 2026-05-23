import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
from datetime import datetime, timedelta
import pymongo
from pymongo import UpdateOne, ReplaceOne
from pymongo import errors

# 获取生产计划
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
        self.furnace_collection = self.db.LabResultSteel

    def fetch_furnace_time_data(self):
        try:
            if not self.is_db_connected():
                logging.info("数据库连接异常")
                return

            # ---------- 改动：从数据库获取最近时间 ----------
            # 查询 ModifiedAt 最大的文档（即最近同步过的时间）
            last_doc = self.furnace_collection.find_one(
                {"ModifiedAt": {"$exists": True}},
                sort=[("ModifiedAt", -1)],
                projection={"ModifiedAt": 1}
            )
            if last_doc and last_doc.get("ModifiedAt"):
                last_time = last_doc["ModifiedAt"]
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

            # 1. 提取所有 SampleId，查询现有文档（用于判断是否需要更新）
            sample_ids = [item["SampleId"] for item in data_list if "SampleId" in item]
            existing_docs = {}
            for doc in self.furnace_collection.find({"SampleId": {"$in": sample_ids}}):
                existing_docs[doc["SampleId"]] = doc

            operations = []
            for item in data_list:
                sample_id = item["SampleId"]
                existing = existing_docs.get(sample_id)

                if existing:
                    # 比较时移除 MongoDB 自动生成的 _id
                    existing_clean = {k: v for k, v in existing.items() if k != '_id'}
                    if existing_clean == item:
                        continue  # 数据无变化，跳过

                # 需要插入或更新 → 使用 ReplaceOne 完整替换（保证文档结构与 API 返回一致）
                operations.append(
                    ReplaceOne(
                        {"SampleId": sample_id},  # 用 SampleId 作为过滤条件
                        item,  # 直接用整个 item 作为新文档
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
                logging.info("没有需要写入的数据（所有样本均无变化）")

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
    mes_client = MESClient("http://10.10.30.57", "XclMesApi/mes-sendTo-L2-LF3", "GetLabResultsSteel", "LabResultSteel", "HeatName")
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