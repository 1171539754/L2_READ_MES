import requests
from datetime import datetime
from typing import Optional

def send_heat_event(
    heat_name: str,
    car_no: int,
    event_code: int,
    site_no: int,
    event_timestamp: Optional[datetime] = None,
    process_stage: int = 0,
    ladle_destination: int = 0,
    server: str = "localhost",
    port: int = 80,
    timeout: int = 10
) -> requests.Response:
    """
    发送炉次事件（HeatEvent）到 MES 系统。

    :param heat_name: 炉次号
    :param car_no: 车号，1-车A，2-车B
    :param event_code: 事件代码，1-炉次开始，2-炉次结束，3-取样委托等
    :param event_timestamp: 事件发生时间（datetime 对象），若为 None 则使用当前时间
    :param process_stage: 取样委托类型，仅当 event_code=3 时有效，否则应填 0
    :param ladle_destination: 炉次结束时的钢包去向，仅当 event_code=2 时有效，否则应填 0
    :param site_no: 站点编号，1-1#LF，2-2#LF
    :param server: 服务器地址
    :param port: 端口号
    :param timeout: 请求超时时间（秒）
    :return: requests.Response 对象
    """
    # 若未提供时间戳，使用当前 UTC 时间（或本地时间，根据业务需求）
    if event_timestamp is None:
        event_timestamp = datetime.now()

    # 构造请求体
    payload = {
        "HeatName": heat_name,
        "CarNo": car_no,
        "EventCode": event_code,
        "EventTimeStamp": event_timestamp.isoformat(),  # ISO8601 格式
        "ProcessStage": process_stage,
        "LadleDestination": ladle_destination,
        "SiteNo": site_no
    }

    # 构造 URL
    url = f"http://{server}:{port}/api/HeatEvent"

    # 发送 POST 请求
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()  # 如果状态码不是 2xx，抛出异常
        return response
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        raise