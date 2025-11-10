"""
UWB 定位客户端

这是一个接口模板，用户需要根据实际的 UWB 系统实现具体的通信逻辑。

接口要求:
  - position 属性或 get_position() 方法：返回 (x, y, z) 元组
  - stop() 方法：停止客户端并释放资源（可选）

使用示例:
    from uwb import UWBClient

    # 创建客户端
    uwb_client = UWBClient(device_name='drone1', host='192.168.31.200', port=8888)

    # 获取位置
    position = uwb_client.position  # 或 uwb_client.get_position()
    if position:
        x, y, z = position
        print(f"位置: ({x:.2f}, {y:.2f}, {z:.2f})m")

    # 停止
    uwb_client.stop()
"""

import time
import socket
import threading
from typing import Optional, Tuple


class UWBClient:
    """
    UWB 定位客户端（模板实现）

    用户需要根据实际 UWB 系统的通信协议修改此类。

    属性:
        position: (x, y, z) 位置坐标（米），数据不可用时为 None
    """

    def __init__(self, device_name: str, host: str = '192.168.31.200', port: int = 8888):
        """
        初始化 UWB 客户端

        Args:
            device_name: 设备名称/ID
            host: UWB 服务器地址
            port: UWB 服务器端口
        """
        self.device_name = device_name
        self.host = host
        self.port = port

        self.position: Optional[Tuple[float, float, float]] = None
        self._running = False
        self._thread = None

        # 启动数据接收线程
        self._start()

    def _start(self):
        """启动数据接收线程"""
        self._running = True
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()
        print(f"[UWB] 客户端已启动: {self.device_name}@{self.host}:{self.port}")

    def _receive_loop(self):
        """
        数据接收循环（用户需要根据实际协议修改）

        示例1: UDP 接收
        示例2: TCP 连接
        示例3: 串口通信
        示例4: HTTP 轮询
        """
        # ==================== 示例实现（UDP） ====================
        # 用户需要根据实际 UWB 系统修改此部分

        try:
            # 创建 UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', self.port))
            sock.settimeout(1.0)

            print(f"[UWB] 监听 UDP 端口: {self.port}")

            while self._running:
                try:
                    # 接收数据
                    data, addr = sock.recvfrom(1024)

                    # 解析数据（示例格式: "drone1,1.23,4.56,0.50"）
                    # 用户需要根据实际协议修改解析逻辑
                    message = data.decode('utf-8').strip()
                    parts = message.split(',')

                    if len(parts) >= 4 and parts[0] == self.device_name:
                        x = float(parts[1])
                        y = float(parts[2])
                        z = float(parts[3])
                        self.position = (x, y, z)

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[UWB] 解析数据错误: {e}")
                    time.sleep(0.1)

        except Exception as e:
            print(f"[UWB] 连接错误: {e}")
        finally:
            if 'sock' in locals():
                sock.close()

        # ==================== 其他实现方式示例 ====================

        # 示例: TCP 客户端
        # try:
        #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #     sock.connect((self.host, self.port))
        #     sock.settimeout(1.0)
        #
        #     while self._running:
        #         try:
        #             data = sock.recv(1024)
        #             if not data:
        #                 break
        #             # 解析数据...
        #         except socket.timeout:
        #             continue
        # except Exception as e:
        #     print(f"[UWB] TCP连接错误: {e}")
        # finally:
        #     sock.close()

        # 示例: 串口通信
        # import serial
        # try:
        #     ser = serial.Serial(port='/dev/ttyUSB0', baudrate=115200, timeout=1.0)
        #     while self._running:
        #         line = ser.readline().decode('utf-8').strip()
        #         # 解析数据...
        # except Exception as e:
        #     print(f"[UWB] 串口错误: {e}")
        # finally:
        #     ser.close()

        # 示例: HTTP 轮询
        # import requests
        # while self._running:
        #     try:
        #         response = requests.get(f"http://{self.host}:{self.port}/position/{self.device_name}")
        #         data = response.json()
        #         self.position = (data['x'], data['y'], data['z'])
        #     except Exception as e:
        #         print(f"[UWB] HTTP请求错误: {e}")
        #     time.sleep(0.1)

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """
        获取当前位置

        Returns:
            (x, y, z) 位置坐标（米），数据不可用时返回 None
        """
        return self.position

    def stop(self):
        """停止客户端"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        print(f"[UWB] 客户端已停止: {self.device_name}")

    def __del__(self):
        """析构函数，确保资源释放"""
        self.stop()


# ==================== Mock UWB 客户端（用于测试） ====================

class MockUWBClient:
    """
    模拟 UWB 客户端（用于测试）

    生成固定位置或简单轨迹，方便测试控制系统。
    """

    def __init__(self, device_name: str, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """
        Args:
            device_name: 设备名称
            x, y, z: 固定位置坐标（米）
        """
        self.device_name = device_name
        self.position = (x, y, z)
        print(f"[MockUWB] 模拟客户端已创建: {device_name} @ ({x:.2f}, {y:.2f}, {z:.2f})")

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """返回固定位置"""
        return self.position

    def stop(self):
        """空操作"""
        print(f"[MockUWB] 模拟客户端已停止: {self.device_name}")


# ==================== 使用示例 ====================

if __name__ == '__main__':
    import time

    # 测试 Mock UWB 客户端
    print("测试 Mock UWB 客户端:")
    mock_client = MockUWBClient('drone1', x=1.0, y=2.0, z=0.5)
    print(f"位置: {mock_client.get_position()}")
    mock_client.stop()

    print("\n" + "="*50 + "\n")

    # 测试真实 UWB 客户端（需要修改实现）
    print("测试真实 UWB 客户端:")
    print("注意: 需要根据实际 UWB 系统修改 _receive_loop() 方法")

    # uwb_client = UWBClient('drone1', host='192.168.31.200', port=8888)
    # try:
    #     for i in range(10):
    #         pos = uwb_client.get_position()
    #         if pos:
    #             print(f"[{i}] 位置: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})m")
    #         else:
    #             print(f"[{i}] 位置数据不可用")
    #         time.sleep(1.0)
    # finally:
    #     uwb_client.stop()
