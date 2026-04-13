import json


#mq发送信息
def mq_send(exchange,channel,body,key):
    json_str = json.dumps(body)
    bytes_data = json_str.encode('utf-8')
    channel.basic_publish(exchange=exchange,
                          routing_key=key,  # 可以用for循环，不用像这样一个一个加
                          body=bytes_data,
                          durable=True
                          )

