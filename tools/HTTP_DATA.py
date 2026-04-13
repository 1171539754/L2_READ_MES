import json
import pymongo
from pymongo.errors import PyMongoError


def gas_report_get(heatid):
    dbclient = pymongo.MongoClient("mongodb://localhost:27017/")
    mydb = dbclient["VOD"]
    gas_report = mydb["sensor_data"]
    try:
        gas_array = gas_report.find({"heatid":str(heatid)})
        # gas_array = gas_report.find({"heatid":'680af8787efd1e0a76a58f52'})

        list1= list(gas_array)
        co = []
        co2 = []
        o2 = []
        result_list1 = {}
        result_list = {}
        for item in list1:
            co.append(round(item['co'], 6))
            co2.append(round(item['co2'], 6))
            o2.append(round(item['o2'], 6))

        result_list["success"]=True
        result_list1["CO"] = co
        result_list1["CO2"]=co2
        result_list1["O2"]=o2
        result_list1["category"] = []
        result_list["data"]=result_list1
        print(result_list)
        return   json.dumps(result_list)
    except PyMongoError as e:
        return json.dumps({"success": False, "error": str(e)})
