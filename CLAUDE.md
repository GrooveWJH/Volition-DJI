# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL DEVELOPMENT PRINCIPLES ⚠️

### 🚨 **AVOID COMPLEXITY AT ALL COSTS!** 🚨

**THIS IS THE MOST IMPORTANT RULE - COMPLEXITY IS THE ENEMY OF FUNCTIONALITY!**

- **NEVER add features that weren't explicitly requested**
- **NEVER create "robust" or "enterprise-grade" solutions**
- **ALWAYS choose the simplest working solution**
- **ALWAYS prefer direct implementation over abstraction**

**Remember: Simple code that works > Complex code that "handles edge cases"**

## Technical Constraints & Requirements

### 🏗️ UI/Controller Separation (MANDATORY)

Business logic MUST be in separate Controller classes:

```javascript
// ✅ GOOD: Pure business logic - no DOM dependencies
export class DrcModeController {
  constructor() {
    this.status = 'idle';
    this.config = {};
  }

  async enterDrcMode() {
    const result = await topicServiceManager.callService(sn, 'drc_mode_enter', this.config);
    return result;  // No direct UI updates
  }
}

// ✅ GOOD: Thin DOM adapter - delegates all business logic
export class DrcModeCardUI {
  constructor() {
    this.controller = new DrcModeController();  // Composition

    if (typeof document !== 'undefined') {
      this.bindElements();  // Only DOM code here
    }

    return cardStateManager.register(this.controller, 'cardId');
  }
}
```

### 🔧 Service Layer Usage

Use Topic Service Layer for all MQTT communication:

```javascript
// ✅ GOOD: Modern service call
const result = await topicServiceManager.callService(sn, 'cloud_control_auth', data);

// ❌ BAD: Direct MQTT (avoid for new code)
const connection = mqttManager.getConnection(sn);
await connection.publish(topic, data);
```

### 🐛 Debugging Rules

**NEVER use console.log() - ALWAYS use debugLogger:**

```javascript
import debugLogger from '#lib/debug.js';

debugLogger.info('Basic information', data);
debugLogger.error('Error occurred', error);
debugLogger.mqtt('MQTT-related logs', message);
debugLogger.service('Service call logs', result);
debugLogger.state('State change logs', newState);
```

### 📊 State Management

All cards MUST use cardStateManager:

```javascript
import { deviceContext, cardStateManager } from '#lib/state.js';

// CRITICAL: Register controller (not UI class) for state management
return cardStateManager.register(this.controller, 'cardId', { debug: true });

// State properties must be serializable (no DOM, functions, circular refs)
this.status = 'active';  // ✅ GOOD
this.element = document.getElementById('foo');  // ❌ BAD
```

### 🔌 MQTT Connection Rules

- Never create MQTT connections manually - use `window.mqttManager`
- Connection pool managed globally with `station-{SN}` client IDs
- Environment detection: `if (typeof document !== 'undefined')` for DOM access

## Project Overview

This repository contains multiple components for DJI drone operations:

- **`grounstation/`**: DJI drone ground station web application (Astro-based)
- **`scripts/python/djisdk/`**: Python SDK for DJI Cloud API (MQTT-based drone control)
- **`mqtt-refcode/`**: MQTT reference implementations and utilities
- **`scripts/`**: Automation and utility scripts

### Ground Station (JavaScript/TypeScript)
The **ground station web application** provides real-time video streaming, MQTT-based remote control (DRC), and multi-device management capabilities.

### Python SDK (djisdk)
The **Python SDK** is a minimal library for DJI drone control via MQTT. It follows the "Good Taste" principle with:
- Only 2 core classes (~150 lines)
- Pure function business layer (stateless services)
- No complex design patterns
- 92% test coverage (42 unit tests)

## Development Commands

### Ground Station (Astro Web App)

```bash
cd grounstation

# Development server (runs on port 4321)
pnpm dev

# Debug console (PRIMARY debugging method)
# http://localhost:4321/debug
```

### Python SDK (djisdk)

```bash
cd scripts/python

# Install dependencies
pip install paho-mqtt rich

# Run CLI tool (interactive DRC control)
python -m djisdk.cli.drc_control --sn <GATEWAY_SN> --username <USER> --password <PASS>

# Run MQTT sniffer (multi-topic monitor)
python utils/mqtt_sniffer.py

# Run all tests (42 tests, ~92% coverage)
python tests/run_tests.py

# Run specific test module
python tests/run_tests.py test_mqtt_client

# Run single test with unittest
python -m unittest tests.test_mqtt_client.TestMQTTClient.test_connect -v
```

## Path Aliases (from grounstation/)

- `#lib/*` → `src/lib/*`
- `#cards/*` → `src/cards/*`
- `#components/*` → `src/components/*`
- `#config/*` → `src/config/*`

## Python SDK Architecture (djisdk)

### Core Design Philosophy
**"Simplicity is the ultimate sophistication"** - The SDK is intentionally minimal:
- **2 core classes**: `MQTTClient` (connection) + `ServiceCaller` (RPC)
- **Pure functions**: All business logic is stateless
- **No abstractions**: Direct, straightforward code flow
- **Zero duplication**: `_call_service()` wrapper eliminates 90% repetition

### Directory Structure
```
scripts/python/djisdk/
├── core/
│   ├── mqtt_client.py      # MQTT connection + Future-based responses
│   └── service_caller.py   # Sync wrapper around async MQTT
├── services/
│   ├── commands.py         # ALL DJI services in one file (167 lines)
│   └── heartbeat.py        # Background thread (special case)
├── cli/
│   └── drc_control.py      # Interactive CLI tool
└── tests/                  # 42 unit tests, 92% coverage
```

### Adding New Services
**Super simple** - add 1-2 lines to `services/commands.py`:

```python
# djisdk/services/commands.py

def send_joystick(caller: ServiceCaller, pitch: float, roll: float, yaw: float, throttle: float):
    """Send virtual joystick command"""
    return _call_service(caller, "drc_joystick", {"pitch": pitch, "roll": roll, "yaw": yaw, "throttle": throttle})
```

Then export in `services/__init__.py` and `djisdk/__init__.py`. That's it!

### Key Patterns

**Request-Response Flow:**
```python
# ServiceCaller creates unique tid → MQTTClient publishes → Future waits → Response sets result
result = caller.call("drc_mode_enter", data)  # Blocks until response or timeout
```

**Heartbeat (Special Case):**
```python
# Background thread, different topic (/drc/down), no response expected
thread = start_heartbeat(mqtt, interval=0.2)  # Returns thread handle
stop_heartbeat(thread)  # Cleanup
```

**Testing Pattern:**
```python
# Mock external dependencies, test in isolation
@patch('djisdk.core.mqtt_client.mqtt.Client')
def test_connect(self, mock_mqtt_client):
    # Test without real MQTT broker
```

### Common Pitfalls
- ❌ Don't create classes for services - use pure functions
- ❌ Don't duplicate try/except - use `_call_service()` wrapper
- ❌ Don't use `HeartbeatKeeper` class (removed) - use `start_heartbeat()` function
- ✅ Always test new services with unit tests
- ✅ Keep business logic in `commands.py`, not in core classes