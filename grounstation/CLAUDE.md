# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **DJI drone ground station web application** built with Astro, providing real-time video streaming, MQTT-based remote control (DRC), and multi-device management capabilities. The architecture supports multiple drones simultaneously with isolated state management per device.

## Development Commands

```bash
# Development server (runs on port 4321)
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview

# Type checking
astro check
```

## Architecture

### Core Concepts

1. **Multi-Device Management**: The system manages multiple DJI drones (identified by SN - Serial Number) simultaneously. Each device maintains independent state and MQTT connections.

2. **Card-Based UI**: The interface is organized into functional "Cards" (e.g., DrcControlCard, StreamingCard). Each card is a self-contained Astro component with its own controllers and services.

3. **Three-Layer State System**:
   - **Device Context** (`device-context.js`): Tracks currently selected device SN
   - **Card State Manager** (`card-state-manager.js`): Proxy-based state isolation per (SN, CardID)
   - **MQTT Connection Manager** (`mqtt-connection-manager.js`): Connection pool per device SN

### Key Architectural Patterns

#### State Proxy Injection Pattern

Cards use JavaScript Proxy to automatically save/restore state when switching devices:

```javascript
// In any Card constructor:
return cardStateManager.register(this, 'cardId', {
  debug: true  // optional
});

// All property assignments are automatically proxied:
this.status = 'active';  // Auto-saved to DeviceStateManager[currentSN]['cardId']
```

This pattern allows cards to maintain separate state for each device without manual state management.

#### Topic Service Layer Architecture

Modern abstraction layer for MQTT service calls:
- **JSON Configuration**: Services defined in `topic-templates.json` for easy manual editing
- **Template Manager**: Parses config and builds topic/message structures
- **Service Manager**: High-level API for service calls with timeout/retry handling
- **Message Router**: Unified message routing with rule-based dispatching

```javascript
// Modern service call pattern:
import topicServiceManager from '@/shared/services/topic-service-manager.js';

const result = await topicServiceManager.callService(sn, 'cloud_control_auth', {
  user_id: 'pilot123',
  user_callsign: 'Station1'
});
```

#### MQTT Connection Pool

Global singleton manages MQTT connections:
- **ClientID format**: `station-{SN}`
- **Auto-connect**: Triggers when device is selected
- **Connection persistence**: Connections stay alive until device goes offline
- **Access**: `window.mqttManager.getCurrentConnection()`

Never create MQTT connections manually in Cards.

### Directory Structure

```
src/
├── cards/                    # Feature cards (DrcControl, Streaming, etc.)
│   └── [CardName]/
│       ├── [CardName].astro  # Astro component (UI)
│       ├── controllers/      # Business logic
│       ├── config/           # Card-specific config
│       └── [feature-modules] # Workflow, auth, etc.
├── lib/                      # Core library (consolidated)
│   ├── state.js             # State management (device context, card state, proxies)
│   ├── mqtt.js              # MQTT connection pool and client wrappers
│   ├── services.js          # Service layer (topic service, message router, templates)
│   ├── devices.js           # Device management and EMQX scanning
│   ├── utils.js             # Utilities (validation, events, helpers)
│   └── debug.js             # Centralized logging system
├── config/                   # Configuration files
│   ├── index.js             # Unified configuration (app, cards, mqtt, video)
│   └── topic-templates.json # Service definitions (JSON)
├── components/               # Shared UI components
│   ├── DroneDeviceSwitcher.astro  # Top device selector
│   └── CollapsibleCard.astro      # Card wrapper
└── pages/
    ├── index.astro           # Main ground station
    ├── debug.astro           # Debug console (like Linux dmesg)
    └── api/
        └── emqx-clients.js   # Simplified EMQX API (direct fetch)
```

### Data Flow for Device Switching

```
User clicks device SN-2 in DeviceSwitcher
    ↓
DeviceContext.setCurrentDevice('SN-2')
    ↓
    ├─→ Triggers 'device-changed' event
    │       ↓
    │   CardStateManager listens
    │       ↓
    │   All CardStateProxy instances:
    │       - Save SN-1 state snapshot
    │       - Load SN-2 state from DeviceStateManager
    │       - Trigger 'card-state-restored' event
    │           ↓
    │       Cards call updateUI()
    │
    └─→ MqttConnectionManager listens
            ↓
        ensureConnection('SN-2')
            ↓
        Creates/reuses MQTT connection for SN-2
            ↓
        DeviceSwitcher indicator → blue (connected)
```

## Critical Integration Points

### Adding a New Card

1. Create card in `src/cards/[CardName]/`
2. In Card's controller constructor:
   ```javascript
   import { cardStateManager } from '@/lib/state.js';

   constructor() {
     // Define state properties
     this.status = 'idle';
     this.logs = [];

     this.init();

     // MUST return proxy
     return cardStateManager.register(this, 'uniqueCardId');
   }

   init() {
     // Listen for device switch
     window.addEventListener('card-state-restored', () => {
       this.updateUI();
     });
   }
   ```

3. Add to `src/config/index.js`:
   ```javascript
   export const CARD_CONFIG = {
     uniqueCardId: {
       id: 'unique-card-id',
       collapsed: false,
       title: 'Card Title',
       description: 'Description'
     }
   };
   ```

4. Import and use in `src/pages/index.astro`

### Using MQTT in a Card

Modern approach using Topic Service Layer:

```javascript
import { topicServiceManager } from '@/lib/services.js';

// Service call (preferred method)
const result = await topicServiceManager.callService(sn, 'cloud_control_auth', {
  user_id: 'pilot123',
  user_callsign: 'Station1'
});

if (result.success) {
  console.log('Service successful:', result.data);
} else {
  console.error('Service failed:', result.error);
}
```

Legacy direct MQTT approach (avoid for new code):

```javascript
import { mqttManager } from '@/lib/mqtt.js';

// Get current device connection
const connection = mqttManager.getCurrentConnection();

if (connection && connection.isConnected) {
  // Subscribe
  connection.subscribe('topic', (message) => {
    console.log(message);
  });

  // Publish
  await connection.publish('topic', { data: 'value' });
}
```

## Configuration Files

- **`config/index.js`**: Unified configuration (app, cards, mqtt, video, emqx settings)
- **`config/topic-templates.json`**: Service definitions with topic templates, timeouts, parameters (JSON format for easy manual editing)

## Important Constraints

1. **Use Topic Service Layer for new MQTT code**: Prefer `topicServiceManager.callService()` over direct MQTT
2. **Never modify Card business logic for state management**: Use CardStateManager proxy pattern
3. **Never create MQTT connections manually**: Use `window.mqttManager`
4. **State properties must be serializable**: No DOM elements, functions, or circular references
5. **Card controllers are singletons**: Exported as `new ClassName()` at bottom of file
6. **Astro SSR mode**: Components run on server, use `is:inline` scripts for client-side JS
7. **Use centralized logging**: Import from `@/lib/debug.js` instead of `console.log/error/warn`

## Device Discovery

Devices are discovered via EMQX HTTP API (`devices.js`):
- Polls EMQX `/api/v5/clients` endpoint every 3 seconds
- Filters clients matching DJI RC regex: `/^[A-Z0-9]{14}$/`
- Updates `DeviceManager` which triggers UI refresh

## Debugging

### Debug Console (Web Interface)

Access debug logs via web interface: `http://localhost:4321/debug`
- Real-time log streaming (like Linux dmesg)
- Advanced filtering by level, source, time range
- Search functionality and log export
- No need to open browser console

### Programmatic Debugging

```javascript
// Use centralized logger (replaces console.log)
import debugLogger from '@/lib/debug.js';

debugLogger.service('Service call completed', result);
debugLogger.mqtt('Message received', message);
debugLogger.state('Device state changed', newState);
debugLogger.error('Connection failed', error);

// Check device state
import { deviceContext, deviceStateManager, cardStateManager } from '@/lib/state.js';
deviceContext.getSummary()

// Check all card states
cardStateManager.debug()
deviceStateManager.getAllStates()

// Check MQTT connections
import { mqttManager } from '@/lib/mqtt.js';
mqttManager.getStats()
mqttManager.getConnectionsInfo()

// Enable card proxy debug mode
cardStateManager.register(this, 'myCard', { debug: true });
```

## Path Aliases

- `@/` → `src/` (configured in tsconfig.json)

## Tech Stack

- **Astro 4.15**: SSR framework
- **Tailwind CSS**: Styling with Material Design utilities
- **MQTT.js 5.10**: WebSocket MQTT client
- **Tippy.js**: Tooltips for device aliases
- **TypeScript**: Type checking (strict mode disabled)

## Common Patterns

### Event-Driven Communication

Global events used for cross-component communication:
- `device-changed`: Device selection changed
- `card-state-restored`: Card state loaded after device switch
- `mqtt-connection-changed`: MQTT connection state changed
- Custom card events (e.g., `drc:step-changed`)

### localStorage Keys

- `current_device_sn`: Last selected device
- `device_aliases`: Device nickname mapping
- `device_state_{SN}_{cardId}`: Per-device card state
- `emqx_*`: EMQX API config
- `mqtt_broker_*`: MQTT connection config

## Testing Multi-Device Functionality

1. Configure EMQX in DeviceSwitcher settings
2. Ensure multiple DJI devices are connected to EMQX
3. Select SN-1, perform actions (DRC, logging, etc.)
4. Switch to SN-2 (should show clean state)
5. Switch back to SN-1 (state should be fully restored)
6. Refresh page (states should persist via localStorage)

## Known Limitations

- WebSocket MQTT only (no native TCP)
- Page refresh breaks connections briefly (1s reconnection delay)
- Card state limited by localStorage quota (~5-10MB)
- EMQX API polling interval: 3 seconds (not real-time)
