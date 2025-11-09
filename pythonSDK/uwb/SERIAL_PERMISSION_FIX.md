# 串口权限永久配置指南

## 问题说明

访问 `/dev/ttyACM0` 需要 `dialout` 组权限。虽然你已经通过 `sudo usermod -a -G dialout $USER` 添加到该组，但**组权限的变更需要重新登录才能在你的 shell 会话中生效**。

## ✅ 已完成的配置

```bash
sudo usermod -a -G dialout groove
```

这个命令已经**永久**将你添加到 dialout 组。下次登录后会自动生效。

## 🔧 立即生效的解决方案

在当前终端中，你需要**激活新的组权限**，有以下几种方式：

### 方案 1：使用 newgrp 命令（最简单）

在你的终端中运行：

```bash
newgrp dialout
```

然后在**同一个终端**中运行程序：

```bash
python uwb/getdata_smoothed_web.py
```

**注意**：`newgrp` 会启动一个新的 shell，当你 `exit` 这个 shell 后会回到原来的 shell。

### 方案 2：重新登录（永久生效）

完全退出当前登录会话，然后重新登录。这样新的组权限会在所有终端中永久生效。

```bash
# 在终端中
logout
# 或者按 Ctrl+D
# 然后重新登录
```

### 方案 3：临时权限（不推荐，每次重启失效）

如果你不想重新登录，可以临时修改设备权限：

```bash
sudo chmod 666 /dev/ttyACM0
```

**缺点**：这个权限在设备重新插拔或系统重启后会失效。

## 验证权限是否生效

运行以下命令检查你当前会话的组权限：

```bash
groups
```

输出中应该包含 `dialout`。

或者更详细的检查：

```bash
id | grep dialout
```

如果没有输出，说明当前会话还没有激活 dialout 组权限。

## 测试串口访问

```bash
# 检查串口设备权限
ls -l /dev/ttyACM0

# 输出应该类似：
# crw-rw---- 1 root dialout 166, 0 Nov  9 19:40 /dev/ttyACM0
#                   ^^^^^^^
#                   你需要在这个组中

# 尝试读取串口（Ctrl+C 退出）
cat /dev/ttyACM0
```

如果 `cat` 命令能执行（即使看到乱码），说明权限已经生效。

## 推荐流程

```bash
# 1. 在终端中激活 dialout 组
newgrp dialout

# 2. 验证组权限
groups  # 应该看到 dialout

# 3. 运行程序
cd /home/groove/work/Volition-DJI/pythonSDK
python uwb/getdata_smoothed_web.py

# 4. 打开浏览器访问
# http://localhost:8050
```

## 永久性说明

✅ **已永久配置**：你的用户账户已经被添加到 dialout 组，这是永久性的。

✅ **下次登录自动生效**：从下次登录开始，所有新的终端会话都会自动拥有 dialout 组权限。

✅ **无需 sudo**：配置完成后，你可以直接访问 `/dev/ttyACM*` 设备，无需 sudo。

## 故障排查

### 问题：运行 `newgrp dialout` 后仍然权限错误

**解决**：确保在**同一个终端**中运行 python 程序。`newgrp` 只影响当前 shell。

### 问题：`groups` 命令显示了 dialout，但程序仍然报错

**解决**：
1. 完全退出终端并重新打开
2. 或者重启系统
3. 或者使用 `exec su -l $USER` 重新加载用户环境

### 问题：设备路径不是 /dev/ttyACM0

**解决**：
```bash
# 查找所有串口设备
ls -l /dev/tty* | grep dialout

# 或者使用 dmesg 查看最近插入的设备
dmesg | tail -20

# 修改程序中的 SERIAL_PORT 配置
# uwb/getdata_smoothed_web.py 第 46 行
```

---

**总结**：运行 `newgrp dialout`，然后在同一终端运行程序即可！
