# coding=utf-8
### 生产者
import pika
import json


user_info = pika.PlainCredentials('guest', 'guest')  # 用户名和密码
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='localhost',          # 主机地址
        port=5672,                 # 端口
        virtual_host='/',          # 虚拟主机
        credentials=user_info,     # 认证信息
        heartbeat=120      ,        # 心跳间隔（秒），600=10分钟

    )
)
channel = connection.channel()
channel.exchange_declare(exchange='exchangedirect',exchange_type='direct',passive=True,durable=True)


def send(message,key):
    json_str = json.dumps(message)
    bytes_data = json_str.encode('utf-8')
    channel.basic_publish(exchange='exchangedirect',
                          routing_key=key,
                          body=bytes_data,

                          )
