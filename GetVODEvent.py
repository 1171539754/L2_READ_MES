
import time

from apscheduler.schedulers.background import BackgroundScheduler
import requests
import logging
from datetime import datetime, timedelta
import pymongo
from pymongo import UpdateOne
from pymongo import errors

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
            # 查询 VODEvent.VOD_HeatStartTime 最大的文档（即最近同步过的时间）
            last_doc = self.furnace_collection.find_one(
                {"VODEvent.VOD_HeatStartTime": {"$exists": True}},
                sort=[("VODEvent.VOD_HeatStartTime", -1)],
                projection={"VODEvent.VOD_HeatStartTime": 1}
            )
            if last_doc and last_doc.get("VODEvent", {}).get("VOD_HeatStartTime"):
                last_time = last_doc["VODEvent"]["VOD_HeatStartTime"]
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

            # 处理 result 本身是列表的情况（你的 API 返回的是列表包字典）
            if isinstance(result, list):
                if not result:
                    logging.info("API返回空列表")
                    return
                result = result[0]  # 取第一个元素作为主字典

            # 检查 Ok 字段
            if not result.get("OK"):
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

                if heat_start_time:
                    if existing is None or existing.get("HeatStartTime") != heat_start_time:
                        update_fields["VOD_HeatStartTime"] = heat_start_time
                        update_fields["VOD_process"] = 1

                if heat_end_time :
                    if existing is None or existing.get("HeatEndTime") != heat_end_time:
                        update_fields["VOD_HeatEndTime"] = heat_end_time
                        update_fields["VOD_process"] = 2

                if state_code :
                    if existing is None or state_code != existing.get("HeatStateCode"):
                        update_fields["VOD_HeatStateCode"] = state_code

                if position_code :
                    if existing is None or position_code != existing.get("PositionCode"):
                        update_fields["VOD_PositionCode"] = position_code

                if not update_fields:
                    continue

                operations.append(
                    UpdateOne(
                        {"HeatName": heat_name},
                        {"$set":
                             {"VODEvent": update_fields,

                              },
                             },

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
    mes_client = MESClient("http://10.10.30.57", "XclMesApi/mes-sendTo-L2-LF3", "GetVODEvent", "VODEvent", "HeatName")
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