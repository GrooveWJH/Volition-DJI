"""
UAV 状态数据模型

统一管理所有数据源的状态快照，消除数据获取逻辑的散乱。

设计原则（Linus "Good Taste"）：
- 数据结构优先：通过统一的数据模型消除特殊情况
- 单一职责：状态构建（数据聚合）与 UI 渲染完全分离
- 清晰的数据流：构建状态 → 决策样式 → 渲染 UI
"""
import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List


@dataclass
class UAVState:
    """
    无人机状态快照（所有数据源的聚合）

    职责：
    1. 聚合来自 MQTT、文件、连接管理器、IVAS 等所有数据源
    2. 提供状态查询方法（颜色、标题等样式决策）
    3. 作为 UI 渲染的唯一数据源（消除重复的数据获取）
    """
    # 基本信息
    uav_id: str
    user_id: str  # 新增：用于显示标题
    sn: str
    callsign: str
    aircraft_sn: Optional[str]
    elapsed: int

    # 连接状态（优先级最高）
    is_online: bool
    is_reconnecting: bool
    is_heartbeat_alive: bool

    # OSD 数据
    osd_frequency: float
    position: Tuple[Optional[float], Optional[float], Optional[float]]  # (lat, lon, height)
    relative_height: Optional[float]
    attitude_head: Optional[float]
    speed: Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]  # (h_speed, x, y, z)
    battery_percent: Optional[int]
    flight_mode_name: str

    # HSI 数据
    local_height: Optional[int]
    is_hsi_ok: bool

    # 任务数据
    mission_metadata: Optional[Dict[str, Any]]
    flyto_progress: Optional[Dict[str, Any]]

    # IVAS 日志
    ivas_logs: List[Dict[str, Any]]

    @classmethod
    def from_uav_client(
        cls,
        uav_client: Dict[str, Any],
        config: Dict[str, str],
        elapsed: int,
        offline_timeout: float = 2.0,
        ivas_adapter = None
    ) -> 'UAVState':
        """
        工厂方法：从各种数据源构建状态快照

        这是唯一需要访问所有数据源的地方。
        UI 渲染代码只需要访问 UAVState 对象，不再需要关心数据从哪来。

        Args:
            uav_client: 无人机客户端数据 (mqtt, caller, heartbeat, connection_manager, ivas)
            config: 无人机配置 (sn, user_id, callsign)
            elapsed: 运行时间（秒）
            offline_timeout: 离线超时时间（秒）
            ivas_adapter: IVAS 适配器（可选）

        Returns:
            UAVState 快照对象
        """
        mqtt = uav_client['mqtt']
        connection_manager = uav_client.get('connection_manager')

        # 心跳状态检查（逻辑集中在这里，只写一次）
        if connection_manager:
            heartbeat = connection_manager.get_heartbeat_thread()
        else:
            heartbeat = uav_client['heartbeat']
        is_heartbeat_alive = heartbeat and heartbeat.is_alive()

        # 任务元数据读取（逻辑集中在这里，只写一次）
        mission_metadata = None
        try:
            mission_state_file = Path('/tmp/djisdk_mission_state.json')
            if mission_state_file.exists():
                with open(mission_state_file, 'r') as f:
                    mission_state = json.load(f)
                mission_metadata = mission_state.get(config.get('callsign'))
        except Exception:
            pass  # 静默失败

        # IVAS 日志读取（逻辑集中在这里，只写一次）
        ivas_logs = []
        if ivas_adapter:
            try:
                ivas_logs = ivas_adapter.get_recent_logs(5)
            except Exception:
                pass  # 静默失败

        # 构建状态快照
        return cls(
            uav_id=uav_client['id'],
            user_id=config.get('user_id', uav_client['id']),  # 使用 config 中的 user_id
            sn=config['sn'],
            callsign=config['callsign'],
            aircraft_sn=mqtt.get_aircraft_sn(),
            elapsed=elapsed,
            is_online=mqtt.is_online(timeout=offline_timeout),
            is_reconnecting=connection_manager.is_reconnecting() if connection_manager else False,
            is_heartbeat_alive=is_heartbeat_alive,
            osd_frequency=mqtt.get_osd_frequency(),
            position=mqtt.get_position(),
            relative_height=mqtt.get_relative_height(),
            attitude_head=mqtt.get_attitude_head(),
            speed=mqtt.get_speed(),
            battery_percent=mqtt.get_battery_percent(),
            flight_mode_name=mqtt.get_flight_mode_name(),
            local_height=mqtt.get_local_height(),
            is_hsi_ok=mqtt.is_local_height_ok(),
            mission_metadata=mission_metadata,
            flyto_progress=mqtt.get_flyto_progress(),
            ivas_logs=ivas_logs,
        )

    # ========== 样式决策方法（消除散落的条件分支）==========

    def get_panel_color(self) -> str:
        """
        面板边框颜色（优先级逻辑）

        优先级：
        1. 重连中 → 黄色
        2. 离线 → 红色
        3. 心跳异常 → 黄色
        4. 正常 → 洋红色
        """
        if self.is_reconnecting:
            return "bright_yellow"
        if not self.is_online:
            return "bright_red"
        if not self.is_heartbeat_alive:
            return "bright_yellow"
        return "bright_magenta"

    def get_panel_title(self) -> str:
        """
        面板标题（包含状态标识）

        使用 user_id 作为主要标识（如 pilot_1, pilot_2）
        """
        base_title = f"[bold]无人机 {self.user_id}[/bold]"

        if self.is_reconnecting:
            return f"{base_title} [bright_yellow]🔄 重连中...[/bright_yellow]"
        if not self.is_online:
            return f"{base_title} [bright_red]● 离线[/bright_red]"
        if not self.is_heartbeat_alive:
            return f"{base_title} [bright_yellow]⚠ 心跳异常[/bright_yellow]"

        return base_title

    def get_freq_color(self) -> str:
        """
        OSD 频率颜色

        规则：
        - 离线：灰色
        - >= 90Hz：绿色
        - >= 50Hz：黄色
        - < 50Hz：红色
        """
        if not self.is_online:
            return "dim"
        if self.osd_frequency >= 60:
            return "bright_green"
        if self.osd_frequency >= 30:
            return "bright_yellow"
        return "bright_red"

    def get_connection_status_text(self) -> str:
        """连接状态文本"""
        return "[bright_green]✓ 在线[/bright_green]" if self.is_online else "[bright_red]✗ 离线[/bright_red]"

    def get_heartbeat_status_text(self) -> str:
        """心跳状态文本"""
        return "[bright_green]✓ 正常[/bright_green]" if self.is_heartbeat_alive else "[bright_red]✗ 异常[/bright_red]"

    def get_mode_color(self) -> str:
        """
        飞行模式颜色

        规则：
        - 自动返航/降落 → 黄色（警告）
        - 未连接/未知 → 红色（错误）
        - 手动/虚拟摇杆/指令 → 青色（手动控制）
        - 其他 → 绿色（正常）
        """
        if self.flight_mode_name in ["自动返航", "自动降落", "强制降落"]:
            return "bright_yellow"
        if self.flight_mode_name in ["未连接", "未知"]:
            return "bright_red"
        if self.flight_mode_name in ["手动飞行", "虚拟摇杆状态", "指令飞行"]:
            return "bright_cyan"
        return "bright_green"
