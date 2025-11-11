#!/usr/bin/env python3
"""
IVAS Task Mock Server - 用于本地测试任务接收和执行

仅模拟 IVAS 任务轮询接口，不包含位置上报、目标检测等其他功能。

功能：
1. 模拟真实 IVAS 服务器的 /outdoorTask 接口（任务轮询）
2. 提供测试接口 /mock/push_task 用于推送任务
3. 维护任务队列（每个设备独立队列）

使用方法：
    python ivas/task_mock_server.py
"""
from flask import Flask, jsonify, request
from collections import deque, defaultdict
from rich.console import Console
from datetime import datetime

app = Flask(__name__)
console = Console()

# 任务队列（每个设备一个队列）
task_queues = defaultdict(deque)

# 统计信息
stats = {
    'tasks_pushed': 0,
    'tasks_fetched': 0,
}


@app.route('/jk-ivas/third/controller/zsLogin', methods=['POST'])
def login():
    """
    模拟 IVAS 登录接口（必需，否则 IVAS Client 无法启动）

    客户端启动时需要登录获取 token。

    Request Body:
        {
            "account": "ZSDX001",
            "password": "000000"
        }

    Returns:
        JSON: {'resCode': 1, 'resData': {'token': 'xxx'}}
    """
    data = request.json or {}
    account = data.get('account', '未知')

    # Mock Server 直接返回成功（不验证密码）
    console.print(
        f"[green]{datetime.now().strftime('%H:%M:%S')} | "
        f"登录请求: account={account}[/green]"
    )

    return jsonify({
        'resCode': 1,  # 1 = 成功
        'resMsg': '登录成功',
        'resData': {
            'token': f'mock-token-{account}'  # 假的 token
        }
    })


@app.route('/jk-ivas/third/controller/outdoorTask', methods=['GET'])
def get_outdoor_task():
    """
    轮询任务接口（模拟真实 IVAS 服务器）

    客户端通过此接口轮询任务。如果有任务，返回任务数据；否则返回空。

    参数:
        deviceCode (int): 设备编号（来自 UAV_CONFIGS 中的 ivas.device_code）

    Returns:
        JSON: {'code': 200, 'data': task_data} 或 {'code': 200, 'data': None}
    """
    # 直接从 query 参数获取 deviceCode
    device_id = request.args.get('deviceCode', type=int)

    if not device_id:
        return jsonify({'code': 400, 'msg': '缺少 deviceCode 参数', 'data': None}), 400

    if device_id in task_queues and task_queues[device_id]:
        task = task_queues[device_id].popleft()
        stats['tasks_fetched'] += 1

        console.print(
            f"[green]{datetime.now().strftime('%H:%M:%S')} | "
            f"设备 {device_id} 拉取任务: mission={task['mission']}[/green]"
        )

        return jsonify({'code': 200, 'msg': '获取任务成功', 'data': task})
    else:
        # 无任务（静默，不打印日志）
        return jsonify({'code': 200, 'msg': '暂无任务', 'data': None})


@app.route('/mock/push_task', methods=['POST'])
def push_task():
    """
    测试接口：推送任务到队列

    用于测试工具（如 keyboard_commander）向指定设备推送任务。

    支持 id=99 广播模式：
    - 如果任务的 id=99 且任务类型为 1/2/3（起飞/降落/返航），则广播到所有设备
    - 如果任务的 id=99 但任务类型为 4/5/6/7，则返回错误（不支持广播）

    Request Body:
        {
            "device_id": 1,  # 推送目标设备（保留向后兼容）
            "task": {"mission": 1, "id": 99, ...}  # id=99 触发广播
        }

    Returns:
        JSON: {'status': 'ok', 'queue_size': N} 或错误信息
    """
    data = request.json
    device_id = data.get('device_id', 1)
    task = data.get('task', {})
    mission = task.get('mission', 0)
    task_id = task.get('id', device_id)  # 使用任务中的 id 字段，默认为 device_id

    # 检查 id=99 广播模式
    if task_id == 99:
        # 任务类型 1/2/3 支持广播
        if mission in [1, 2, 3]:
            mission_names = {1: "起飞10米", 2: "降落", 3: "返航"}
            console.print(
                f"[bold magenta]{datetime.now().strftime('%H:%M:%S')} | "
                f"广播任务到所有设备: {mission_names.get(mission, f'任务{mission}')}[/bold magenta]"
            )

            # 广播到所有设备（假设最多3个设备）
            broadcasted = []
            for target_device in [1, 2, 3]:
                task_queues[target_device].append(task.copy())
                stats['tasks_pushed'] += 1
                broadcasted.append(target_device)

            total_queue_size = sum(len(task_queues[d]) for d in broadcasted)

            console.print(
                f"[bold green]{datetime.now().strftime('%H:%M:%S')} | "
                f"已广播到设备 {broadcasted}，总队列长度: {total_queue_size}[/bold green]"
            )

            return jsonify({
                'status': 'ok',
                'broadcast': True,
                'devices': broadcasted,
                'total_queue_size': total_queue_size
            })

        # 任务类型 4/5/6/7 不支持广播
        elif mission in [4, 5, 6, 7]:
            mission_names = {4: "飞向指定点", 5: "轨迹任务1", 6: "轨迹任务2", 7: "轨迹任务3"}
            error_msg = f"任务类型 {mission_names.get(mission, mission)} 不支持广播（id=99）"

            console.print(
                f"[red]{datetime.now().strftime('%H:%M:%S')} | "
                f"错误: {error_msg}[/red]"
            )

            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 400

    # 普通模式：推送到指定设备
    task_queues[device_id].append(task)
    stats['tasks_pushed'] += 1

    queue_size = len(task_queues[device_id])

    console.print(
        f"[cyan]{datetime.now().strftime('%H:%M:%S')} | "
        f"推送任务到设备 {device_id}: mission={mission}, 队列长度={queue_size}[/cyan]"
    )

    return jsonify({'status': 'ok', 'queue_size': queue_size})


@app.route('/mock/stats', methods=['GET'])
def get_stats():
    """
    获取服务器统计信息

    Returns:
        JSON: 统计数据
    """
    queue_info = {
        device_id: len(queue)
        for device_id, queue in task_queues.items()
    }

    return jsonify({
        'stats': stats,
        'queues': queue_info
    })


@app.route('/mock/clear', methods=['POST'])
def clear_queues():
    """
    清空所有任务队列

    Returns:
        JSON: {'status': 'ok', 'cleared': N}
    """
    cleared_count = sum(len(q) for q in task_queues.values())
    task_queues.clear()

    console.print(f"[yellow]清空所有队列，共清除 {cleared_count} 个任务[/yellow]")

    return jsonify({'status': 'ok', 'cleared': cleared_count})


if __name__ == '__main__':
    console.print("[bold cyan]IVAS Mock Server 启动中...[/bold cyan]")
    console.print("[dim]监听地址: http://localhost:5001[/dim]")
    console.print("[dim]登录接口: POST /jk-ivas/third/controller/zsLogin[/dim]")
    console.print("[dim]轮询接口: GET /jk-ivas/third/controller/outdoorTask?deviceCode=1[/dim]")
    console.print("[dim]推送接口: POST /mock/push_task[/dim]")
    console.print("[dim]统计接口: GET /mock/stats[/dim]")
    console.print("[dim]清空队列: POST /mock/clear[/dim]\n")

    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
