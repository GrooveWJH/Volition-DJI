#!/usr/bin/env python3
"""
纯净版 IVAS + 多DRC 程序

专注于：
1. IVAS 任务接收和分发
2. 多无人机 DRC 控制
3. 任务执行 DEBUG 输出

不包含：
- Dashboard UI
- VRPN 数据
- 无人机状态显示

使用方法：
    python pure.py
"""
import sys
import os
import time
import threading
from typing import Dict, Any, List
from rich.console import Console

# 添加 ivas 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ivas'))

from djisdk import MQTTClient, ServiceCaller
from djisdk import request_control_auth, enter_drc_mode, start_heartbeat, stop_heartbeat
from djisdk.tasks.ivas_executor import execute_ivas_task
from djisdk.tasks import MissionRunner
from ivas import IVASClient

console = Console()

# ========== 配置 ==========

MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot_1',
        'callsign': 'Pilot 1',
        'flight_height': 90.0,
        'ivas': {
            'device_code': 1,
            'account': 'ZSDX001',
            'password': '000000'
        }
    },
    {
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Pilot 2',
        'flight_height': 100.0,
        'ivas': {
            'device_code': 2,
            'account': 'ZSDX002',
            'password': '000000'
        }
    },
    {
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot_3',
        'callsign': 'Pilot 3',
        'flight_height': 110.0,
        'ivas': {
            'device_code': 3,
            'account': 'ZSDX003',
            'password': '000000'
        }
    },
]

IVAS_SERVER = {
    'base_url': 'http://192.168.31.38:8888',
    'task_hz': 2.0,  # 任务轮询频率 (Hz)
}

# 机器颜色映射（用于DEBUG输出）
DEVICE_COLORS = {
    1: 'bright_cyan',
    2: 'bright_magenta',
    3: 'bright_green',
}


# ========== 核心类 ==========

class PureIVASAdapter:
    """
    纯净版 IVAS 适配器

    负责：
    - 接收 TaskDistributor 分发的任务
    - 在后台线程执行任务
    - 输出彩色 DEBUG 日志
    """

    def __init__(self, uav_config: Dict[str, Any], mqtt_config: Dict[str, Any]):
        """
        初始化适配器

        Args:
            uav_config: 无人机配置
            mqtt_config: MQTT 配置
        """
        self.uav_config = uav_config
        self.mqtt_config = mqtt_config
        self.device_code = uav_config['ivas']['device_code']
        self.callsign = uav_config['callsign']
        self.color = DEVICE_COLORS.get(self.device_code, 'bright_white')

        # DRC 组件
        self.mqtt: MQTTClient = None
        self.caller: ServiceCaller = None
        self.heartbeat_thread = None

        # 任务执行
        self.current_runner: MissionRunner = None
        self.task_executor_thread = None
        self.task_lock = threading.Lock()

    def _log(self, level: str, message: str):
        """
        输出彩色日志

        Args:
            level: 日志级别（info/warning/error）
            message: 日志消息
        """
        timestamp = time.strftime("%H:%M:%S")

        # 根据级别选择前缀颜色
        level_colors = {
            'info': 'bright_white',
            'warning': 'bright_yellow',
            'error': 'bright_red',
        }
        level_color = level_colors.get(level, 'bright_white')

        # 格式：[时间戳] [Pilot X] 消息
        console.print(
            f"[dim]{timestamp}[/dim] [{self.color}][{self.callsign}][/{self.color}] "
            f"[{level_color}]{message}[/{level_color}]"
        )

    def setup_drc(self) -> bool:
        """
        建立 DRC 连接

        Returns:
            bool: 成功返回 True
        """
        try:
            # 1. 连接 MQTT
            self._log('info', f"连接 MQTT ({self.mqtt_config['host']}:{self.mqtt_config['port']})...")
            self.mqtt = MQTTClient(self.uav_config['sn'], self.mqtt_config)
            self.mqtt.connect()
            self._log('info', "✅ MQTT 连接成功")

            # 2. 请求控制权
            self._log('info', "请求控制权...")
            self.caller = ServiceCaller(self.mqtt)
            request_control_auth(self.caller, user_id=self.uav_config['user_id'], user_callsign=self.callsign)
            self._log('info', "✅ 控制权获取成功")

            # 3. 进入 DRC 模式
            self._log('info', "进入 DRC 模式...")
            mqtt_broker_config = {
                'address': f"{self.mqtt_config['host']}:{self.mqtt_config['port']}",
                'client_id': f"drc-{self.device_code}",
                'username': self.mqtt_config['username'],
                'password': self.mqtt_config['password'],
                'expire_time': int(time.time()) + 3600,
                'enable_tls': False
            }
            enter_drc_mode(self.caller, mqtt_broker=mqtt_broker_config, osd_frequency=10, hsi_frequency=5)
            self._log('info', "✅ DRC 模式已启动")

            # 4. 启动心跳
            self._log('info', "启动心跳...")
            self.heartbeat_thread = start_heartbeat(self.mqtt, interval=1.0)
            self._log('info', "✅ 心跳已启动")

            return True

        except Exception as e:
            self._log('error', f"❌ DRC 连接失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def receive_task(self, task_data: Dict[str, Any]):
        """
        接收任务（由 TaskDistributor 调用）

        所有任务强制立即执行（立即中断旧任务）。

        Args:
            task_data: IVAS 任务数据
        """
        mission = task_data.get('mission', 0)
        mission_names = {1: "起飞", 2: "降落", 3: "返航", 4: "前往指定点",
                        5: "多航点任务1", 6: "多航点任务2", 7: "多航点任务3"}
        mission_name = mission_names.get(mission, f"任务{mission}")
        target_id = task_data.get('id', 0)

        # 日志输出
        if target_id == 99:
            self._log('info', f"📢 [广播] 接收任务: {mission_name}")
        else:
            self._log('info', f"📥 接收任务: {mission_name}")

        # 停止旧任务（如果存在）
        if self.current_runner and self.current_runner.running:
            self._log('warning', "⚠️ 停止旧任务")
            self.current_runner.stop()

        # 等待旧线程结束（强制模式，仅等待 0.1 秒）
        if self.task_executor_thread and self.task_executor_thread.is_alive():
            self.task_executor_thread.join(timeout=0.1)
            if self.task_executor_thread.is_alive():
                self._log('warning', "⚠️ 旧任务未完全停止，强制启动新任务")

        # 在后台线程执行新任务
        def task_wrapper():
            """任务执行包装器"""
            try:
                self._log('info', f"🔍 开始执行任务 {mission}")

                # 创建 MissionRunner（用于轨迹任务）
                runner_config = {
                    'callsign': self.callsign,
                    'sn': self.mqtt.gateway_sn,
                    'flight_height': self.uav_config['flight_height']
                }
                self.current_runner = MissionRunner(self.mqtt, self.caller, None, runner_config)

                # 执行任务
                execute_ivas_task(
                    mqtt=self.mqtt,
                    caller=self.caller,
                    task_data=task_data,
                    uav_config=self.uav_config,
                    runner=self.current_runner
                )

                self._log('info', f"✅ 任务 {mission} 执行完成")

            except Exception as e:
                self._log('error', f"❌ 任务执行异常: {e}")
                import traceback
                tb_lines = traceback.format_exc().split('\n')[:10]
                for line in tb_lines:
                    if line.strip():
                        self._log('error', f"  {line}")

        # 启动任务线程
        self.task_executor_thread = threading.Thread(target=task_wrapper, daemon=True)
        self.task_executor_thread.start()
        self._log('info', f"🚀 任务线程已启动")

    def cleanup(self):
        """清理资源"""
        self._log('info', "清理资源...")

        # 停止任务
        if self.current_runner:
            self.current_runner.stop()

        # 停止心跳
        if self.heartbeat_thread:
            stop_heartbeat(self.heartbeat_thread)

        # 断开 MQTT
        if self.mqtt:
            self.mqtt.disconnect()

        self._log('info', "✅ 资源清理完成")


class PureTaskDistributor:
    """
    纯净版任务分发器

    负责：
    - 单点轮询 IVAS 服务器
    - 智能路由任务（id=99 广播，id=1/2/3 单播）
    - 任务去重
    """

    def __init__(self, ivas_config: Dict[str, Any]):
        """
        初始化分发器

        Args:
            ivas_config: IVAS 配置（必须包含 base_url, account, password, task_hz）
        """
        self.adapters: Dict[int, PureIVASAdapter] = {}
        self.executed_tasks = set()
        self.lock = threading.Lock()
        self.finalized = False
        self.thread = None

        # 创建 IVASClient（用于轮询）
        # 关键：使用真实的 IVAS 账号密码
        self.ivas_client = IVASClient(
            device_code=0,  # 占位符，不用于过滤
            account=ivas_config['account'],      # 真实账号
            password=ivas_config['password'],    # 真实密码
            base_lat=0.0, base_lon=0.0, base_alt=0.0,
            coord_range={'lat_offset': 0, 'lon_offset': 0, 'alt_offset': 0},
            base_url=ivas_config['base_url'],
            report_hz=0.0,  # 禁用位置上报
            task_hz=ivas_config['task_hz'],
            features={
                'position_report': False,
                'target_report': False,
                'task_receive': True  # 只启用任务轮询
            }
        )

        # 覆盖任务处理方法
        # 直接替换为我们的处理函数（不需要绑定到 ivas_client）
        self.ivas_client._log = lambda log_type, data: self._handle_ivas_log(log_type, data)

        console.print("[bold bright_cyan]📡 TaskDistributor 初始化完成[/bold bright_cyan]")

    def register(self, device_code: int, adapter: PureIVASAdapter):
        """
        注册 adapter

        Args:
            device_code: 设备编号
            adapter: 适配器实例
        """
        with self.lock:
            if self.finalized:
                raise RuntimeError("Cannot register after finalization")
            self.adapters[device_code] = adapter
            console.print(f"[dim]  ✓ 注册设备 {device_code}[/dim]")

    def finalize(self):
        """完成注册"""
        with self.lock:
            self.finalized = True
            console.print(f"[bold green]✅ 注册完成，共 {len(self.adapters)} 个设备[/bold green]")

    def start(self):
        """启动轮询线程"""
        if not self.finalized:
            raise RuntimeError("Must finalize before start")

        self.thread = threading.Thread(target=self.ivas_client.run, daemon=True)
        self.thread.start()
        console.print("[bold green]🚀 IVAS 轮询线程已启动[/bold green]")

    def stop(self):
        """停止轮询"""
        self.ivas_client.stop()
        if self.thread:
            self.thread.join(timeout=2.0)
        console.print("[yellow]⏹️  IVAS 轮询已停止[/yellow]")

    def _handle_ivas_log(self, log_type: str, data: Any):
        """
        处理 IVASClient 的日志输出

        这是任务接收的入口点。

        Args:
            log_type: 日志类型
            data: 日志数据
        """
        if log_type != 'task':
            return

        # 解析任务数据
        if not isinstance(data, dict) or data.get('code') != 200:
            return

        task_data = data.get('data')
        if not task_data:
            return

        target_id = task_data.get('id', 0)
        mission = task_data.get('mission', 0)

        # 路由分发
        if target_id == 99:
            # 广播模式
            self._distribute_broadcast(task_data)
        elif target_id in self.adapters:
            # 单播模式
            console.print(f"[cyan]📨 路由任务到设备 {target_id} (mission={mission})[/cyan]")
            adapter = self.adapters[target_id]
            adapter.receive_task(task_data)
        else:
            console.print(f"[yellow]⚠️  未知任务 ID: {target_id} (mission={mission})[/yellow]")

    def _distribute_broadcast(self, task_data: Dict[str, Any]):
        """
        广播分发

        Args:
            task_data: IVAS 任务数据
        """
        mission = task_data.get('mission', 0)
        mission_names = {1: "起飞", 2: "降落", 3: "返航"}

        # 1. 类型验证：只有 1/2/3 支持广播
        if mission not in [1, 2, 3]:
            console.print(f"[red]❌ 任务 {mission} 不支持广播，仅支持起飞/降落/返航[/red]")
            return

        # 2. 任务去重
        task_signature = f"{mission}_{task_data.get('timestamp', int(time.time()))}"

        with self.lock:
            if task_signature in self.executed_tasks:
                console.print(f"[dim]⏭️  任务 {task_signature} 已执行过，跳过[/dim]")
                return

            self.executed_tasks.add(task_signature)

            # 清理旧记录
            if len(self.executed_tasks) > 100:
                old_tasks = list(self.executed_tasks)[:50]
                for old_task in old_tasks:
                    self.executed_tasks.discard(old_task)

        # 3. 广播分发
        mission_name = mission_names.get(mission, f"任务{mission}")
        console.print(
            f"[bold bright_yellow]📢 广播任务: {mission_name} (ID:99) "
            f"→ {len(self.adapters)} 个设备[/bold bright_yellow]"
        )

        success_count = 0
        for device_code, adapter in self.adapters.items():
            try:
                adapter.receive_task(task_data)
                success_count += 1
                console.print(f"[green]  ✓ 设备 {device_code} 已接收[/green]")
            except Exception as e:
                console.print(f"[red]  ✗ 设备 {device_code} 失败: {e}[/red]")

        console.print(
            f"[bold green]✅ 广播完成: {success_count}/{len(self.adapters)} "
            f"个设备成功接收[/bold green]"
        )


# ========== 主程序 ==========

def main():
    """主函数"""
    console.print("\n[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]")
    console.print("[bold bright_cyan]       纯净版 IVAS + 多DRC 程序[/bold bright_cyan]")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    # 1. 创建任务分发器（使用第一个 IVAS 账号进行轮询）
    console.print("[bold]📡 步骤 1: 初始化任务分发器[/bold]")

    # 获取第一个有效的 IVAS 配置
    first_ivas_config = None
    for config in UAV_CONFIGS:
        if 'ivas' in config:
            first_ivas_config = config['ivas']
            break

    if not first_ivas_config:
        console.print("[red]❌ 没有找到 IVAS 配置，退出程序[/red]")
        return

    # 创建任务分发器，传入账号密码
    distributor = PureTaskDistributor({
        'base_url': IVAS_SERVER['base_url'],
        'account': first_ivas_config['account'],
        'password': first_ivas_config['password'],
        'task_hz': IVAS_SERVER['task_hz']
    })
    console.print(f"[dim]使用账号: {first_ivas_config['account']}[/dim]")
    print()

    # 2. 创建并注册所有适配器
    console.print("[bold]🚁 步骤 2: 初始化无人机适配器[/bold]")
    adapters: List[PureIVASAdapter] = []

    for uav_config in UAV_CONFIGS:
        device_code = uav_config['ivas']['device_code']
        callsign = uav_config['callsign']

        console.print(f"\n[bold bright_cyan]初始化 {callsign} (device_code={device_code})...[/bold bright_cyan]")

        adapter = PureIVASAdapter(uav_config, MQTT_CONFIG)
        adapters.append(adapter)

        # 建立 DRC 连接
        if not adapter.setup_drc():
            console.print(f"[red]❌ {callsign} DRC 连接失败，退出程序[/red]")
            return

        # 注册到分发器
        distributor.register(device_code, adapter)

    print()

    # 3. 启动任务分发
    console.print("[bold]🎯 步骤 3: 启动任务分发[/bold]")
    distributor.finalize()
    distributor.start()
    print()

    # 4. 运行
    console.print("[bold green]✅ 系统就绪，等待 IVAS 任务...[/bold green]")
    console.print("[dim]按 Ctrl+C 退出[/dim]\n")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    try:
        # 主线程等待
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  接收到中断信号，正在退出...[/yellow]")

    finally:
        # 5. 清理资源
        console.print("\n[bold]🧹 清理资源...[/bold]")

        distributor.stop()

        for adapter in adapters:
            adapter.cleanup()

        console.print("[bold green]✅ 程序已退出[/bold green]\n")


if __name__ == '__main__':
    main()
