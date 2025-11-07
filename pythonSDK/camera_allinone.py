#!/usr/bin/env python3
"""
多无人机相机同步控制工具

键盘: ↑回中 ↓向下 p看地面 z放大 x缩小 l低头锁定 q退出
"""
import sys
import time
import tty
import termios
import threading
from concurrent.futures import ThreadPoolExecutor

from djisdk import setup_multiple_drc_connections, stop_heartbeat, reset_gimbal, camera_look_at, set_camera_zoom

# ========== 配置 ==========

MQTT_CONFIG = {'host': 'grve.me', 'port': 1883, 'username': 'dji', 'password': 'lab605605'}

UAV_CONFIGS = [
    # {'name': 'Drone001', 'sn': '9N9CN2J0012CXY', 'callsign': 'Alpha', 'zoom': {'current': 7, 'step': 2, 'min': 2, 'max': 200}},
    {'name': 'Drone002', 'sn': '9N9CN8400164WH', 'callsign': 'Bravo', 'zoom': {'current': 5, 'step': 2, 'min': 2, 'max': 200}},
    # {'name': 'Drone003', 'sn': '9N9CN180011TJN', 'callsign': 'Charlie', 'zoom': {'current': 10, 'step': 2, 'min': 2, 'max': 200}},
]

# ========== 全局状态 ==========

uav_states = {}
stop_flag = False
executor = ThreadPoolExecutor(max_workers=10)
lookdown_lock = False
print_lock = threading.Lock()

# ========== 工具函数 ==========

def log(msg):
    """线程安全打印"""
    with print_lock:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
        sys.stdout.flush()

# ========== 并行控制 ==========

def parallel_run(name, action):
    """并行执行所有无人机的控制指令"""
    log(f">>> {name}")

    def run_single(item):
        cs, state = item
        try:
            action(cs, state)
            log(f"  ✓ {cs}")
        except Exception as e:
            log(f"  ✗ {cs}: {e}")

    list(executor.map(run_single, uav_states.items()))

# ========== 控制函数 ==========

def gimbal_center():
    def action(cs, s):
        reset_gimbal(s['mqtt'], s['mqtt'].get_payload_index() or "88-0-0", 0)
    parallel_run("云台回中", action)

def gimbal_down():
    def action(cs, s):
        reset_gimbal(s['mqtt'], s['mqtt'].get_payload_index() or "88-0-0", 1)
    parallel_run("云台向下", action)

def lookat_ground():
    def action(cs, s):
        lat, lon, h = s['mqtt'].get_position()
        if not lat:
            raise Exception("无GPS")
        target = (h or 0) - 100
        camera_look_at(s['mqtt'], s['mqtt'].get_payload_index() or "88-0-0", lat, lon, target, False)
    parallel_run("看地面", action)

def zoom_in():
    def action(cs, s):
        z = s['config']['zoom']
        z['current'] = min(z['current'] + z['step'], z['max'])
        set_camera_zoom(s['mqtt'], s['mqtt'].get_payload_index() or "88-0-0", z['current'], "zoom")
        log(f"  {cs}: {z['current']}x")
    parallel_run("放大", action)

def zoom_out():
    def action(cs, s):
        z = s['config']['zoom']
        z['current'] = max(z['current'] - z['step'], z['min'])
        set_camera_zoom(s['mqtt'], s['mqtt'].get_payload_index() or "88-0-0", z['current'], "zoom")
        log(f"  {cs}: {z['current']}x")
    parallel_run("缩小", action)

# ========== 低头锁定 ==========

def lookdown_loop():
    """50Hz频率持续发送云台向下指令"""
    while lookdown_lock and not stop_flag:
        for cs, s in uav_states.items():
            try:
                reset_gimbal(s['mqtt'], s['mqtt'].get_payload_index() or "88-0-0", 1)
            except:
                pass
        time.sleep(0.02)  # 50Hz

def toggle_lookdown():
    """切换低头锁定状态"""
    global lookdown_lock
    lookdown_lock = not lookdown_lock
    if lookdown_lock:
        log(">>> 低头锁定 [ON] (50Hz)")
        threading.Thread(target=lookdown_loop, daemon=True).start()
    else:
        log(">>> 低头锁定 [OFF]")

# ========== 状态监控 ==========

def status_loop():
    """定期状态检查（仅警告）"""
    while not stop_flag:
        for cs, s in uav_states.items():
            # 只在异常时打印
            if not s['mqtt'].is_online(timeout=3.0):
                log(f"⚠ {cs}: 连接断开")

        time.sleep(5.0)  # 5秒检查一次

# ========== 键盘输入 ==========

def getch():
    """读取单个字符"""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch

def keyboard_loop():
    """键盘监听循环"""
    global stop_flag
    KEY_MAP = {
        '\x1b[A': gimbal_center,
        '\x1b[B': gimbal_down,
        'p': lookat_ground,
        'z': zoom_in,
        'x': zoom_out,
        'l': toggle_lookdown,
    }

    while not stop_flag:
        try:
            ch = getch()
            if ch == '\x1b':
                ch2 = getch()
                if ch2 == '[':
                    ch = '\x1b[' + getch()
            if ch == 'q':
                log(">>> 退出")
                stop_flag = True
                break
            elif ch in KEY_MAP:
                KEY_MAP[ch]()
        except:
            pass

# ========== 主程序 ==========

def main():
    global stop_flag

    print("\n=== 多无人机相机同步控制 ===\n")
    print("正在连接...")

    connections = setup_multiple_drc_connections(UAV_CONFIGS, MQTT_CONFIG, osd_frequency=1, hsi_frequency=1, skip_drc_setup=False)
    print(f"✓ {len(connections)} 架已连接\n")

    for (mqtt, caller, heartbeat), config in zip(connections, UAV_CONFIGS):
        uav_states[config['callsign']] = {'mqtt': mqtt, 'caller': caller, 'heartbeat': heartbeat, 'config': config}

    print("控制: ↑回中 ↓向下 p看地面 z放大 x缩小 l低头锁定 q退出\n")

    try:
        # 启动状态监控
        threading.Thread(target=status_loop, daemon=True).start()

        # 键盘监听（主线程）
        keyboard_loop()

    except KeyboardInterrupt:
        stop_flag = True

    finally:
        print("\n断开连接...")
        for cs, s in uav_states.items():
            try:
                stop_heartbeat(s['heartbeat'])
                s['mqtt'].disconnect()
                print(f"✓ {cs}")
            except Exception as e:
                print(f"⚠ {cs}: {e}")
        executor.shutdown(wait=False)
        print("✓ 完成\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"异常: {e}")
        import traceback
        traceback.print_exc()
