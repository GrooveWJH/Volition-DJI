# 项目代码说明

本文档简要介绍三个核心文件 `cloud_api_http.py`、`cloud_api_mqtt.py` 和 `couldhtml/login.html` 的作用及运行流程，帮助理解最小化 DJI Cloud API 示例的整体协作方式。

## cloud_api_http.py

- **功能定位**：提供一个 FastAPI Web 服务，供 DJI Pilot 控制器在“其它平台”模式下访问登录页。
- **工作流程**：
  1. 程序启动时读取 `HOST_ADDR`、`USERNAME`、`PASSWORD` 三个环境变量，用于动态填充登录页中的 MQTT 连接信息。
  2. `/login` 路由读取本地 `couldhtml/login.html` 文件，将页面模板返回给控制器。代码中使用 `str.replace` 试图把占位符 `hostnamehere`、`userloginhere`、`userpasswordhere` 替换为环境变量的真实值，不过注意当前实现忘记接收 `replace` 的返回值，实际返回的 HTML 仍是原始模板。
  3. 运行入口使用 `uvicorn.run` 在 `HOST_ADDR:5000` 启动 HTTP 服务，确保控制器能访问到 PC 上的服务页面。

## cloud_api_mqtt.py

- **功能定位**：作为 MQTT 客户端连接本地 EMQX 服务器，接收 DJI 设备的遥测数据，并对部分消息进行自动回复。
- **关键步骤**：
  1. 通过环境变量 `HOST_ADDR` 确定 MQTT Broker 地址（默认端口 1883）。
  2. 根据安装的 `paho-mqtt` 主版本自动选择兼容的 `mqtt.Client` 构造方式，注册 `on_connect` 与 `on_message` 回调。
  3. `on_connect` 成功后订阅 `sys/#` 与 `thing/#` 主题，以便获取控制器和飞行器推送的消息。
  4. `on_message` 对不同主题做解析：
     - `thing/.../status` 且 `method == "update_topo"` 时，构造 `_reply` 消息返回 `{ "result": 0 }` 表示确认。
     - `thing/.../osd` 消息提取飞行器 OSD（姿态/高度/速度等）数据，通过 `handle_osd_message` 格式化打印关键字段，辅助调试。
  5. `client.loop_forever()` 阻塞运行，持续处理网络事件。

## couldhtml/login.html

- **用途**：提供给 DJI Pilot 控制器的本地网页，用来验证应用 Licence 并发起 MQTT 连接。
- **页面逻辑**：
  1. 页面准备固定的 `APP_ID`、`APP_KEY` 与 `LICENSE`，通过 `window.djiBridge.platformVerifyLicense` 验证平台许可。
  2. 点击 “Login” 按钮时，读取页面中的占位符（后续由 `cloud_api_http.py` 填充）形成 MQTT 连接参数：
     - `host`：形如 `tcp://<PC_IP>:1883`
     - `username`、`password`：MQTT 认证信息
  3. 调用 `window.djiBridge.platformLoadComponent("thing", params)` 加载组件，并执行 `thingConnect` 以启动连接；日志输出通过 `<ul id="logs">` 展示交互过程。
  4. “Logout” 触发 `platformUnloadComponent("thing")` 断开连接；“Raport” 按钮用于打印当前组件加载与连接状态。

## 各组件协作方式

1. 在 PC 上启动 EMQX 容器，保证 MQTT 服务可用。
2. 运行 `cloud_api_http.py`，控制器访问 `http://HOST_ADDR:5000/login` 打开登录页面。
3. 登录页调用 `thingConnect` 建立控制器→EMQX 的 MQTT 连接。
4. 同时运行 `cloud_api_mqtt.py` 作为 PC 端客户端，订阅 `thing/#` 主题，接收并打印飞行器遥测数据，并对必要的控制消息作出应答。

通过上述流程，可实现最小化的 DJI Cloud API 交互验证与本地调试。
