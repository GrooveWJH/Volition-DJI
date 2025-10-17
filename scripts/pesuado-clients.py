#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量创建若干 DJI RC 风格 clientId 的 MQTT 客户端，匿名连接到 Broker。
所有配置在文件顶部写死，无需命令行参数。
"""

import random
import string
import time
import paho.mqtt.client as mqtt

# ============================ CONFIG ============================
HOST = "localhost"   # EMQX MQTT 服务器地址（非管理端口）
PORT = 1883               # MQTT 端口
COUNT = 7                 # 客户端数量
KEEPALIVE = 10            # keepalive 秒
CLIENT_PREFIX = ""   # clientId 前缀
TOPIC = "djirc/hello"     # 上线/心跳主题
HEARTBEAT_EVERY_SEC = 5   # 心跳间隔秒（0 表示不发心跳）
ALLOW_ANONYMOUS = True    # Broker 必须允许匿名，否则需用户名密码
# ================================================================

MANDATORY_SERIALS = [
    "9N9CNUGWXLQCYU",
    "9N9CN9HLCDS5WB",
    "9N9CNXEHDRYY4Q",
    "9N9CN8SYZRWUFA",
    "9N9CNJSVH9D3ZJ",
]


def gen_dji_sn() -> str:
    """
    生成 DJI RC 风格序列号：
    以 '9N9CN' 开头，总共 14 位 [A-Z0-9]
    例：9N9CN8400164WH
    """
    prefix = "9N9CN"
    suffix_len = 14 - len(prefix)
    suffix = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(suffix_len))
    return prefix + suffix


def build_client_id(sn: str, prefix: str = CLIENT_PREFIX) -> str:
    """组合 clientId"""
    return f"{prefix}{sn}"


def make_client(client_id: str) -> mqtt.Client:
    """创建匿名 MQTT 客户端"""
    c = mqtt.Client(client_id=client_id, clean_session=True)
    # 设置遗嘱消息（下线提示）
    c.will_set(TOPIC, payload=f"{client_id} offline", qos=0, retain=False)
    return c


def build_serial_list(count: int) -> list[str]:
    """生成连接所需的序列号列表，优先包含手动维护的 SN 集合"""
    mandatory_pool = [sn.strip() for sn in MANDATORY_SERIALS if sn.strip()]
    serials: list[str] = []
    used = set()

    if count < len(mandatory_pool):
        mandatory_target = min(count, 4)
    else:
        mandatory_target = len(mandatory_pool)

    serials.extend(mandatory_pool[:mandatory_target])
    used.update(serials)

    while len(serials) < count:
        sn = gen_dji_sn()
        if sn in used:
            continue
        serials.append(sn)
        used.add(sn)

    return serials


def connect_clients():
    clients = []
    serials = build_serial_list(COUNT)
    for sn in serials:
        client_id = build_client_id(sn)
        c = make_client(client_id)
        c.connect(HOST, PORT, KEEPALIVE)
        c.loop_start()
        c.publish(TOPIC, f"{client_id} online", qos=0, retain=False)
        print(f"[OK] Connected: {client_id}")
        clients.append(c)
        time.sleep(0.1)
    return clients


def main():
    clients = connect_clients()
    print(f"\n✅ {COUNT} 个客户端已连接。按 Ctrl+C 退出。\n")

    try:
        if HEARTBEAT_EVERY_SEC > 0:
            while True:
                c = random.choice(clients)
                cid = c._client_id.decode() if isinstance(c._client_id, (bytes, bytearray)) else str(c._client_id)
                c.publish(TOPIC, f"{cid} heartbeat", qos=0)
                time.sleep(HEARTBEAT_EVERY_SEC)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止中...")
    finally:
        for c in clients:
            try:
                c.loop_stop()
                c.disconnect()
            except Exception:
                pass
        print("全部客户端已断开。")


if __name__ == "__main__":
    main()
