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
- **`mqtt-refcode/`**: MQTT reference implementations and utilities
- **`scripts/`**: Automation and utility scripts

The main focus is the **ground station web application** which provides real-time video streaming, MQTT-based remote control (DRC), and multi-device management capabilities.

## Development Commands

```bash
cd grounstation

# Development server (runs on port 4321)
pnpm dev

# Debug console (PRIMARY debugging method)
# http://localhost:4321/debug
```

## Path Aliases (from grounstation/)

- `#lib/*` → `src/lib/*`
- `#cards/*` → `src/cards/*`
- `#components/*` → `src/components/*`
- `#config/*` → `src/config/*`