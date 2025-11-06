# IVAS 接口调用说明

本文档详细说明 IVAS SDK 与服务器交互的操作顺序和数据包格式。

## 📊 可视化说明

本文档包含多个 PlantUML 图表，帮助理解系统交互流程：

- **时序图 (Sequence Diagram)**: 展示客户端与服务器之间的消息交互
- **活动图 (Activity Diagram)**: 展示主循环的业务流程
- **状态机图 (State Diagram)**: 展示 Token 的状态变化

> **提示**: 使用支持 PlantUML 的 Markdown 查看器（如 VSCode + PlantUML 插件、IntelliJ IDEA）可以看到图形化的流程图。

## 目录

1. [操作流程](#操作流程)
2. [接口详细说明](#接口详细说明)
3. [数据包格式](#数据包格式)
4. [完整调用示例](#完整调用示例)

---

## 操作流程

### 整体流程图

#### ASCII 流程图

```
┌─────────────┐
│  1. 登录     │  获取 token
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  2. 主循环   │  携带 token 进行后续操作
└──────┬──────┘
       │
       ├──► 3. 上报位置数据 (高频: 1Hz)
       │
       ├──► 4. 上报目标数据 (高频: 1Hz)
       │
       └──► 5. 轮询任务指令 (低频: 0.2Hz)
             │
             ├─► 检测到 401 错误 → 重新执行步骤 1
             │
             └─► 继续循环
```

#### PlantUML 时序图

```plantuml
@startuml
skinparam responseMessageBelowArrow true
skinparam backgroundColor #FEFEFE
skinparam sequenceArrowThickness 2

actor "无人机客户端" as Client
participant "IVAS 服务器" as Server

== 1. 初始化：登录获取 Token ==
Client -> Server: POST /jk-ivas/third/controller/zsLogin\n{"account": "ZSDX001", "password": "xxx"}
Server --> Client: 200 OK\n{"resCode": 1, "resData": {"token": "xxx"}}
note right: 获取 token 用于后续请求

== 2. 主循环：数据上报和任务轮询 ==
loop 每秒循环 (1Hz)
    Client -> Server: POST /jk-ivas/third/controller/reportUserData\nHeader: token=xxx\nParams: deviceCode, userX, userY, userZ...
    Server --> Client: 200 OK\n{"resCode": 0, "resMsg": "操作成功"}
    note right: 上报位置数据

    Client -> Server: POST /jk-ivas/non/controller/postTarPos\nHeader: token=xxx\nBody: {"timestamp": xxx, "obj_cnt": n, "objs": [...]}
    Server --> Client: 200 OK\n{"resCode": 0, "resMsg": "成功"}
    note right: 上报目标检测数据
end

loop 每 5 秒 (0.2Hz)
    Client -> Server: GET /jk-ivas/third/controller/outdoorTask\nHeader: token=xxx
    Server --> Client: 200 OK\n{"code": 200, "data": {"mission": n, "id": x, ...}}
    note right: 轮询任务指令
end

== 3. 异常处理：Token 过期 ==
Client -> Server: POST /jk-ivas/third/controller/reportUserData\nHeader: token=expired_token
Server --> Client: 401 Unauthorized
note right: Token 过期
Client -> Server: POST /jk-ivas/third/controller/zsLogin\n重新登录
Server --> Client: 200 OK\n新的 token
Client -> Server: 重试之前失败的请求\nHeader: token=new_token
Server --> Client: 200 OK

@enduml
```

### 详细步骤

#### 步骤 1: 系统登录
- **时机**: 启动时 / Token 过期后
- **目的**: 获取 token 用于后续 API 调用
- **接口**: `/jk-ivas/third/controller/zsLogin`

#### 步骤 2-4: 循环上报（主循环）
- **高频任务** (默认 1Hz):
  - 步骤 2: 上报无人机位置
  - 步骤 3: 上报目标检测数据

- **低频任务** (默认 0.2Hz):
  - 步骤 4: 轮询服务器任务

#### 步骤 5: 错误处理
- 检测到 `401 Unauthorized` → 自动重新登录

### 主循环活动图

```plantuml
@startuml
skinparam backgroundColor #FEFEFE
skinparam activityBackgroundColor #E3F2FD
skinparam activityBorderColor #1976D2
skinparam activityDiamondBackgroundColor #FFF9C4
skinparam activityDiamondBorderColor #F57C00

start

:执行登录\n获取 Token;

if (登录成功?) then (yes)
  :保存 Token;

  while (运行中?) is (yes)
    fork
      :记录循环开始时间;

      :上报位置数据\n(reportUserData);

      if (HTTP 401?) then (yes)
        :重新登录;
        :重试位置上报;
      endif

      :上报目标数据\n(postTarPos);

      if (HTTP 401?) then (yes)
        :重新登录;
        :重试目标上报;
      endif

    fork again
      if (距离上次轮询 >= 5秒?) then (yes)
        :轮询任务指令\n(outdoorTask);

        if (HTTP 401?) then (yes)
          :重新登录;
          :重试任务轮询;
        endif

        :更新轮询时间;
      endif
    end fork

    :计算已用时间;
    :睡眠保持频率\n(1Hz);

  endwhile (stop)

  :停止客户端;

else (no)
  :登录失败，退出;
endif

stop

@enduml
```

### Token 状态机图

```plantuml
@startuml
skinparam backgroundColor #FEFEFE
skinparam stateBorderColor #1976D2
skinparam stateBackgroundColor #E3F2FD

[*] --> 未登录

未登录 --> 登录中 : 调用 login()
登录中 --> 已登录 : 登录成功\n获取 token
登录中 --> 登录失败 : 登录失败
登录失败 --> 登录中 : 重试

已登录 --> 使用中 : 开始上报数据

使用中 : 执行位置上报
使用中 : 执行目标上报
使用中 : 执行任务轮询

使用中 --> Token过期 : 收到 401
Token过期 --> 登录中 : 重新登录
Token过期 --> [*] : 登录失败次数过多

使用中 --> 已停止 : 调用 stop()
已停止 --> [*]

@enduml
```

---

## 接口详细说明

### 1. 系统登录

#### 基本信息
- **接口地址**: `/jk-ivas/third/controller/zsLogin`
- **请求方式**: `POST`
- **Content-Type**: `application/json`

#### 请求头
```
Content-Type: application/json
```

#### 请求体格式
```json
{
  "account": "ZSDX001",
  "password": "000000"
}
```

#### 请求参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| account | String | 是 | 用户账号 |
| password | String | 是 | 用户密码 |

#### 响应格式
```json
{
  "resCode": 1,
  "resMsg": "成功",
  "resData": {
    "login": {
      "id": 129,
      "userName": "ZSDX001",
      "account": "ZSDX001",
      "createTime": 1761245456000
    },
    "token": "eyJhbGciOiJIUzUxMiJ9..."
  },
  "data": null
}
```

#### 响应码说明
| resCode | 说明 |
|---------|------|
| 1 | 成功 |
| 2 | 传入参数有误 |
| 40 | 未登录 |
| 50 | 未授权 |
| -1 | 失败 |
| -10 | 服务器内部错误 |

#### Python 实现示例
```python
import requests

url = "http://localhost:5001/jk-ivas/third/controller/zsLogin"
payload = {
    "account": "ZSDX001",
    "password": "000000"
}

response = requests.post(url, json=payload, timeout=5)
result = response.json()

if result['resCode'] == 1:
    token = result['resData']['token']
    print(f"登录成功，token: {token}")
else:
    print(f"登录失败: {result['resMsg']}")
```

#### 登录时序图

```plantuml
@startuml
skinparam responseMessageBelowArrow true

participant "Client" as C
participant "IVAS Server" as S

C -> S: POST /jk-ivas/third/controller/zsLogin
note right
  Content-Type: application/json
  Body:
  {
    "account": "ZSDX001",
    "password": "000000"
  }
end note

alt 登录成功
  S --> C: 200 OK
  note left
    {
      "resCode": 1,
      "resMsg": "成功",
      "resData": {
        "token": "eyJhbGci...",
        "login": {...}
      }
    }
  end note
  C -> C: 保存 token

else 登录失败
  S --> C: 200 OK
  note left
    {
      "resCode": 2,
      "resMsg": "账号或密码错误"
    }
  end note
  C -> C: 处理登录失败

else 服务器错误
  S --> C: 500 Internal Server Error
  C -> C: 记录错误日志
end

@enduml
```

---

### 2. 无人机位置上报

#### 基本信息
- **接口地址**: `/jk-ivas/third/controller/reportUserData`
- **请求方式**: `POST`
- **参数传递**: URL Query String (所有参数通过 URL 传递)

#### 请求头
```
token: eyJhbGciOiJIUzUxMiJ9...
```

#### URL 参数格式
```
http://localhost:5001/jk-ivas/third/controller/reportUserData?deviceCode=1&userX=23.123456&userY=113.456789&userZ=100.5&azimuth=90&localTime=1730851200000&motion=1&validCount=8&roomId=22&refPositionType=0
```

#### 请求参数说明
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| deviceCode | Long | 是 | 设备编号 | 1 |
| userX | BigDecimal | 是 | 纬度 | 23.123456 |
| userY | BigDecimal | 是 | 经度 | 113.456789 |
| userZ | BigDecimal | 是 | 海拔高度 | 100.5 |
| azimuth | Integer | 是 | 方位角 (0-359) | 90 |
| localTime | Long | 是 | 时间戳（毫秒） | 1730851200000 |
| motion | Integer | 是 | 运动状态 (0:静止, 1:移动) | 1 |
| validCount | Integer | 是 | GPS 卫星数 | 8 |
| roomId | Long | 是 | 任务 ID (固定传 22) | 22 |
| refPositionType | Integer | 是 | 设备类型 (固定传 0) | 0 |
| ivasUserInfoId | Long | 否 | 人员 ID | - |
| userName | String | 否 | 用户名称 | - |

#### 响应格式
```json
{
  "data": {},
  "resCode": 0,
  "resData": {},
  "resMsg": "操作成功"
}
```

#### Python 实现示例
```python
import requests
import time

url = "http://localhost:5001/jk-ivas/third/controller/reportUserData"
headers = {
    "token": "eyJhbGciOiJIUzUxMiJ9..."
}
params = {
    "deviceCode": 1,
    "userX": 23.123456,
    "userY": 113.456789,
    "userZ": 100.5,
    "azimuth": 90,
    "localTime": int(time.time() * 1000),  # 毫秒时间戳
    "motion": 1,
    "validCount": 8,
    "roomId": 22,
    "refPositionType": 0
}

response = requests.post(url, params=params, headers=headers, timeout=3)
print(f"位置上报响应: {response.json()}")
```

---

### 3. 目标检测位置上报

#### 基本信息
- **接口地址**: `/jk-ivas/non/controller/postTarPos`
- **请求方式**: `POST`
- **Content-Type**: `application/json`

#### 请求头
```
Content-Type: application/json
token: eyJhbGciOiJIUzUxMiJ9...
```

#### 请求体格式
```json
{
  "timestamp": 1725465600,
  "obj_cnt": 2,
  "objs": [
    {
      "id": 1001,
      "cls": 0,
      "gis": [113.456789, 23.123456, 15.2],
      "bbox": [320.5, 240.0, 50.0, 80.0],
      "obj_img": "http://example.com/images/obj_1001.jpg"
    },
    {
      "id": 1002,
      "cls": 1,
      "gis": [113.457, 23.124, 0.0],
      "bbox": [450.0, 300.0, 80.0, 60.0],
      "obj_img": "http://example.com/images/obj_1002.jpg"
    }
  ]
}
```

#### 请求参数说明

**顶层参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| timestamp | Integer | 是 | 时间戳（秒） |
| obj_cnt | Integer | 是 | 检测到的目标数量 |
| objs | List | 是 | 目标对象列表 |

**objs 数组元素参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | Integer | 否 | 目标唯一标识 |
| cls | Integer | 是 | 目标类别 (0:人, 1:车, 2:飞机) |
| gis | Double[3] | 是 | [经度, 纬度, 海拔] |
| bbox | Double[4] | 否 | [X坐标, Y坐标, 宽度, 高度] |
| obj_img | String | 否 | 目标图片 URL |

#### 响应格式
```json
{
  "data": {},
  "resCode": 0,
  "resData": {},
  "resMsg": "成功"
}
```

#### Python 实现示例
```python
import requests
import time

url = "http://localhost:5001/jk-ivas/non/controller/postTarPos"
headers = {
    "Content-Type": "application/json",
    "token": "eyJhbGciOiJIUzUxMiJ9..."
}
payload = {
    "timestamp": int(time.time()),
    "obj_cnt": 2,
    "objs": [
        {
            "id": 1001,
            "cls": 0,  # 人
            "gis": [113.456789, 23.123456, 15.2],
            "bbox": [320.5, 240.0, 50.0, 80.0],
            "obj_img": "http://example.com/images/obj_1001.jpg"
        },
        {
            "id": 1002,
            "cls": 1,  # 车
            "gis": [113.457, 23.124, 0.0],
            "bbox": [450.0, 300.0, 80.0, 60.0],
            "obj_img": "http://example.com/images/obj_1002.jpg"
        }
    ]
}

response = requests.post(url, json=payload, headers=headers, timeout=3)
print(f"目标上报响应: {response.json()}")
```

---

### 4. 室外任务轮询

#### 基本信息
- **接口地址**: `/jk-ivas/third/controller/outdoorTask`
- **请求方式**: `GET`

#### 请求头
```
token: eyJhbGciOiJIUzUxMiJ9...
```

#### 响应格式
```json
{
  "code": 200,
  "msg": "获取任务成功",
  "data": {
    "mission": 4,
    "id": 1,
    "lon": 113.473701,
    "lat": 23.230416,
    "alt": 50.5
  }
}
```

#### 响应参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| mission | Integer | 任务类型（见下方枚举） |
| id | Integer | 指定无人机 ID (99=所有无人机) |
| lat | Float | 纬度（任务类型 4 需要） |
| lon | Float | 经度（任务类型 4 需要） |
| alt | Float | 高度（任务类型 4 需要） |

#### 任务类型枚举
| mission 值 | 说明 | 是否需要坐标 | 是否可指定所有无人机 |
|-----------|------|--------------|---------------------|
| 1 | 原地起飞 5 米 | 否 | 是 (id=99) |
| 2 | 原地降落 | 否 | 是 (id=99) |
| 3 | 返航 | 否 | 是 (id=99) |
| 4 | 前往指定点 | 是 (lat, lon, alt) | 否 |
| 5 | 预设多航点任务 1 | 否 | 否 |
| 6 | 预设多航点任务 2 | 否 | 否 |
| 7 | 预设多航点任务 3 | 否 | 否 |

#### Python 实现示例
```python
import requests

url = "http://localhost:5001/jk-ivas/third/controller/outdoorTask"
headers = {
    "token": "eyJhbGciOiJIUzUxMiJ9..."
}

response = requests.get(url, headers=headers, timeout=3)
result = response.json()

if result['code'] == 200:
    task_data = result['data']
    print(f"收到任务: 类型={task_data['mission']}, 目标ID={task_data['id']}")

    if task_data['mission'] == 4:  # 前往指定点
        print(f"目标坐标: ({task_data['lat']}, {task_data['lon']}, {task_data['alt']})")
```

#### 任务轮询时序图

```plantuml
@startuml
skinparam responseMessageBelowArrow true

participant "Client" as C
participant "IVAS Server" as S

loop 每 5 秒轮询
  C -> S: GET /jk-ivas/third/controller/outdoorTask
  note right: Header: token=xxx

  alt 有任务
    S --> C: 200 OK
    note left
      {
        "code": 200,
        "data": {
          "mission": 4,
          "id": 1,
          "lat": 23.230416,
          "lon": 113.473701,
          "alt": 50.5
        }
      }
    end note
    C -> C: 解析任务\n执行相应操作

  else 无任务
    S --> C: 200 OK
    note left
      {
        "code": 200,
        "data": null
      }
    end note

  else Token 过期
    S --> C: 401 Unauthorized
    C -> S: POST /jk-ivas/third/controller/zsLogin\n重新登录
    S --> C: 200 OK (新 token)
    C -> S: GET /jk-ivas/third/controller/outdoorTask\n重试任务轮询
    S --> C: 200 OK
  end
end

@enduml
```

---

## 数据包格式

### 数据包结构总览

```
请求流程:
┌─────────────────────────────────────────────────────────┐
│ 1. 登录请求                                              │
│    POST /jk-ivas/third/controller/zsLogin               │
│    Content-Type: application/json                       │
│    Body: {"account": "xxx", "password": "xxx"}          │
│                                                          │
│ ↓ 响应获取 token                                         │
│                                                          │
│ 2. 位置上报 (循环)                                       │
│    POST /jk-ivas/third/controller/reportUserData        │
│    Header: token=xxx                                     │
│    Query String: deviceCode=1&userX=23.0&...            │
│                                                          │
│ 3. 目标上报 (循环)                                       │
│    POST /jk-ivas/non/controller/postTarPos              │
│    Header: token=xxx, Content-Type=application/json     │
│    Body: {"timestamp": xxx, "obj_cnt": 2, "objs": [...]}│
│                                                          │
│ 4. 任务轮询 (循环)                                       │
│    GET /jk-ivas/third/controller/outdoorTask            │
│    Header: token=xxx                                     │
└─────────────────────────────────────────────────────────┘
```

### 完整数据包示例

#### 1. 登录请求包
```http
POST /jk-ivas/third/controller/zsLogin HTTP/1.1
Host: localhost:5001
Content-Type: application/json
Content-Length: 49

{"account":"ZSDX001","password":"000000"}
```

**响应包:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "resCode": 1,
  "resMsg": "成功",
  "resData": {
    "login": {
      "id": 129,
      "userName": "ZSDX001",
      "account": "ZSDX001",
      "createTime": 1761245456000
    },
    "token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjkiLCJuYmYiOjE3NjEyNzQyNjgsImlzcyI6Iml2YXNfdGhpcmQiLCJ1c2VyTmFtZSI6IlpTRFgwMDEiLCJ1dWlkIjp7ImxlYXN0U2lnbmlmaWNhbnRCaXRzIjotNzA2MTA2MjcyMzQ0MTc2MDcyMiwibW9zdFNpZ25pZmljYW50Qml0cyI6LTQyMzQ2NTE1NjYxMzU2ODgzODd9LCJpYXQiOjE3NjEyNzQyNjh9.t9TtbuEn-HfeplMPNeR-r41dbnMDTB_YkZ2SZdr5RgQHGIK6txqJRgzUFgLqj_Dq1KO3vxQMS7QWlB5viWPh_g"
  },
  "data": null
}
```

#### 2. 位置上报请求包
```http
POST /jk-ivas/third/controller/reportUserData?deviceCode=1&userX=23.123456&userY=113.456789&userZ=100.5&azimuth=90&localTime=1730851200000&motion=1&validCount=8&roomId=22&refPositionType=0 HTTP/1.1
Host: localhost:5001
token: eyJhbGciOiJIUzUxMiJ9...
```

**响应包:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "data": {},
  "resCode": 0,
  "resData": {},
  "resMsg": "操作成功"
}
```

#### 3. 目标上报请求包
```http
POST /jk-ivas/non/controller/postTarPos HTTP/1.1
Host: localhost:5001
Content-Type: application/json
token: eyJhbGciOiJIUzUxMiJ9...
Content-Length: 287

{
  "timestamp": 1725465600,
  "obj_cnt": 1,
  "objs": [
    {
      "id": 1001,
      "cls": 0,
      "gis": [113.473701, 23.230416, 15.2],
      "bbox": [320.5, 240.0, 50.0, 80.0],
      "obj_img": "http://example.com/images/obj_1001.jpg"
    }
  ]
}
```

**响应包:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "data": {},
  "resCode": 0,
  "resData": {},
  "resMsg": "成功"
}
```

#### 4. 任务轮询请求包
```http
GET /jk-ivas/third/controller/outdoorTask HTTP/1.1
Host: localhost:5001
token: eyJhbGciOiJIUzUxMiJ9...
```

**响应包:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "code": 200,
  "msg": "获取任务成功",
  "data": {
    "mission": 4,
    "id": 1,
    "lon": 113.473701,
    "lat": 23.230416,
    "alt": 50.5
  }
}
```

---

## 完整调用示例

### Python 完整示例

```python
import requests
import time
import random

class IVASClientExample:
    def __init__(self, base_url, account, password, device_code):
        self.base_url = base_url
        self.account = account
        self.password = password
        self.device_code = device_code
        self.token = None

    def login(self):
        """步骤 1: 登录获取 token"""
        url = f"{self.base_url}/jk-ivas/third/controller/zsLogin"
        payload = {
            "account": self.account,
            "password": self.password
        }

        response = requests.post(url, json=payload, timeout=5)
        result = response.json()

        if result['resCode'] == 1:
            self.token = result['resData']['token']
            print(f"✓ 登录成功")
            return True
        else:
            print(f"✗ 登录失败: {result['resMsg']}")
            return False

    def report_position(self, lat, lon, alt):
        """步骤 2: 上报位置"""
        url = f"{self.base_url}/jk-ivas/third/controller/reportUserData"
        headers = {"token": self.token}
        params = {
            "deviceCode": self.device_code,
            "userX": lat,
            "userY": lon,
            "userZ": alt,
            "azimuth": random.randint(0, 359),
            "localTime": int(time.time() * 1000),
            "motion": 1,
            "validCount": 8,
            "roomId": 22,
            "refPositionType": 0
        }

        response = requests.post(url, params=params, headers=headers, timeout=3)

        if response.status_code == 401:
            print("Token 过期，重新登录...")
            self.login()
            return self.report_position(lat, lon, alt)

        print(f"✓ 位置上报成功")
        return response.json()

    def report_targets(self):
        """步骤 3: 上报目标"""
        url = f"{self.base_url}/jk-ivas/non/controller/postTarPos"
        headers = {
            "token": self.token,
            "Content-Type": "application/json"
        }

        obj_cnt = random.randint(0, 3)
        objs = []
        for _ in range(obj_cnt):
            objs.append({
                "id": random.randint(1000, 9999),
                "cls": random.randint(0, 2),
                "gis": [113.456 + random.uniform(-0.001, 0.001),
                        23.123 + random.uniform(-0.001, 0.001),
                        random.uniform(0, 20)],
                "bbox": [random.uniform(0, 1920),
                         random.uniform(0, 1080),
                         random.uniform(50, 200),
                         random.uniform(50, 200)],
                "obj_img": f"http://example.com/img/{random.randint(1, 100)}.jpg"
            })

        payload = {
            "timestamp": int(time.time()),
            "obj_cnt": obj_cnt,
            "objs": objs
        }

        response = requests.post(url, json=payload, headers=headers, timeout=3)

        if response.status_code == 401:
            print("Token 过期，重新登录...")
            self.login()
            return self.report_targets()

        print(f"✓ 目标上报成功 (检测到 {obj_cnt} 个目标)")
        return response.json()

    def poll_task(self):
        """步骤 4: 轮询任务"""
        url = f"{self.base_url}/jk-ivas/third/controller/outdoorTask"
        headers = {"token": self.token}

        response = requests.get(url, headers=headers, timeout=3)

        if response.status_code == 401:
            print("Token 过期，重新登录...")
            self.login()
            return self.poll_task()

        result = response.json()
        if result['code'] == 200 and result.get('data'):
            task = result['data']
            print(f"✓ 收到任务: 类型={task['mission']}, 目标ID={task['id']}")
        else:
            print("✓ 暂无任务")

        return result

    def run(self, duration=60):
        """运行客户端"""
        if not self.login():
            return

        start_time = time.time()
        last_task_poll = 0

        while time.time() - start_time < duration:
            # 高频: 位置和目标上报 (1Hz)
            self.report_position(23.123456, 113.456789, 100.0)
            self.report_targets()

            # 低频: 任务轮询 (0.2Hz = 5秒)
            if time.time() - last_task_poll >= 5:
                self.poll_task()
                last_task_poll = time.time()

            time.sleep(1)  # 1Hz

        print(f"\n运行完成，共 {duration} 秒")


# 使用示例
if __name__ == "__main__":
    client = IVASClientExample(
        base_url="http://localhost:5001",
        account="ZSDX001",
        password="000000",
        device_code=1
    )

    # 运行 60 秒
    client.run(duration=60)
```

---

## 错误处理

### 常见错误码

| HTTP 状态码 | 说明 | 处理方法 |
|------------|------|----------|
| 200 | 成功 | 继续执行 |
| 401 | Token 过期/未授权 | 重新登录 |
| 403 | 禁止访问 | 检查权限 |
| 404 | 接口不存在 | 检查 URL |
| 500 | 服务器错误 | 联系服务器管理员 |

### 401 错误自动处理示例

```python
def request_with_auto_retry(self, method, url, **kwargs):
    """自动处理 token 过期的请求"""
    headers = kwargs.get('headers', {})
    headers['token'] = self.token
    kwargs['headers'] = headers

    if method == 'POST':
        response = requests.post(url, **kwargs)
    else:
        response = requests.get(url, **kwargs)

    # 检测 401 错误
    if response.status_code == 401:
        print("Token 过期，重新登录...")
        if self.login():
            # 重试请求
            headers['token'] = self.token
            if method == 'POST':
                response = requests.post(url, **kwargs)
            else:
                response = requests.get(url, **kwargs)

    return response
```

---

## 注意事项

1. **时间戳格式**:
   - 登录接口响应中的 `createTime`: 毫秒时间戳
   - 位置上报的 `localTime`: 毫秒时间戳
   - 目标上报的 `timestamp`: 秒时间戳

2. **坐标顺序**:
   - 位置上报: `userX=纬度, userY=经度`
   - 目标 gis: `[经度, 纬度, 海拔]` (注意顺序不同！)

3. **Token 管理**:
   - Token 应该在请求头中携带，key 为 `token`
   - 检测到 401 错误立即重新登录
   - Token 有效期需要咨询服务器管理员

4. **频率控制**:
   - 建议位置上报: 1-10 Hz
   - 建议任务轮询: 0.1-1 Hz
   - 根据实际需求和服务器性能调整

5. **必填参数**:
   - `roomId` 固定传 22
   - `refPositionType` 固定传 0
   - `azimuth` 没有则传 0
   - `validCount` 没有则传 0

---

## 附录

### 完整的类型定义 (TypeScript 风格)

```typescript
// 登录请求
interface LoginRequest {
  account: string;
  password: string;
}

// 登录响应
interface LoginResponse {
  resCode: number;
  resMsg: string;
  resData: {
    login: {
      id: number;
      userName: string;
      account: string;
      createTime: number;
    };
    token: string;
  };
  data: null;
}

// 位置上报参数
interface PositionParams {
  deviceCode: number;
  userX: number;        // 纬度
  userY: number;        // 经度
  userZ: number;        // 海拔
  azimuth: number;      // 0-359
  localTime: number;    // 毫秒时间戳
  motion: number;       // 0或1
  validCount: number;
  roomId: number;       // 固定22
  refPositionType: number;  // 固定0
}

// 目标上报请求
interface TargetRequest {
  timestamp: number;    // 秒时间戳
  obj_cnt: number;
  objs: Array<{
    id?: number;
    cls: number;        // 0,1,2
    gis: [number, number, number];  // [经度, 纬度, 海拔]
    bbox?: [number, number, number, number];  // [x, y, w, h]
    obj_img?: string;
  }>;
}

// 任务响应
interface TaskResponse {
  code: number;
  msg: string;
  data: {
    mission: number;    // 1-7
    id: number;
    lat?: number;
    lon?: number;
    alt?: number;
  };
}
```

---

**文档版本**: 1.0.0
**最后更新**: 2025-11-06
