#!/usr/bin/env python3
"""
简单的本地 MQTT 测试脚本。

功能：
1. 连接指定的 MQTT 服务器（默认 localhost:1883）。
2. 订阅测试主题（默认 test/topic）。
3. 发布一条测试消息，确认收发流程是否正常。

使用示例：
    python mqtt_local_test.py --host localhost --port 1883 --topic demo/topic
"""

import argparse
import json
import sys
import time

import paho.mqtt.client as mqtt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地 MQTT 连通性测试")
    parser.add_argument("--host", default="localhost", help="MQTT 服务器地址")
    parser.add_argument("--port", type=int, default=1883, help="MQTT 服务器端口")
    parser.add_argument(
        "--topic", default="test/topic", help="用于测试的订阅/发布主题"
    )
    parser.add_argument(
        "--message",
        default="hello from mqtt_local_test.py",
        help="发布的测试消息内容",
    )
    parser.add_argument(
        "--username", help="MQTT 用户名（如不需要可省略）", default=None
    )
    parser.add_argument(
        "--password", help="MQTT 密码（如不需要可省略）", default=None
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(
        f"准备连接 MQTT -> host={args.host} port={args.port} topic={args.topic}"
    )

    client = mqtt.Client()
    if args.username:
        client.username_pw_set(args.username, args.password)

    def on_connect(client, userdata, flags, rc):
        readable = mqtt.connack_string(rc)
        print(f"[on_connect] result={readable}")
        if rc == 0:
            client.subscribe(args.topic)
            print(f"[on_connect] 已订阅主题: {args.topic}")

    def on_message(client, userdata, msg):
        print(
            "[on_message]",
            json.dumps(
                {
                    "topic": msg.topic,
                    "payload": msg.payload.decode("utf-8", errors="ignore"),
                },
                ensure_ascii=False,
            ),
        )

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(args.host, args.port, keepalive=60)
    except Exception as exc:
        print(f"连接失败: {exc}")
        return 1

    client.loop_start()

    time.sleep(1)  # 等待连接建立

    payload = f"{args.message} @ {time.strftime('%Y-%m-%d %H:%M:%S')}"
    result = client.publish(args.topic, payload=payload, qos=0)
    print(f"已发布测试消息 -> rc={result.rc} payload={payload}")

    try:
        time.sleep(3)  # 等待回环消息
    finally:
        client.loop_stop()
        client.disconnect()
        print("MQTT 测试完成，已断开连接")

    return 0


if __name__ == "__main__":
    sys.exit(main())
