/**
 * 设备管理器
 */

import deviceContext from '@/shared/core/device-context.js';
import { scanDevices } from '@/shared/services/device-scanner.js';

const DJI_RC_REGEX = /^[A-Z0-9]{14}$/;

class DeviceManager {
  constructor() {
    this.devices = new Map();
    this.timer = null;
    this.listeners = [];
  }

  start() {
    this.scan();
    this.timer = setInterval(() => this.scan(), 3000);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
  }

  async scan() {
    const clientIds = await scanDevices();
    const rcDevices = clientIds.filter(id => DJI_RC_REGEX.test(id));

    let hasChanges = false;

    // 检查离线设备
    for (const dev of this.devices.values()) {
      const wasOnline = dev.online;
      dev.online = rcDevices.includes(dev.sn);

      if (wasOnline !== dev.online) {
        hasChanges = true;
      }
    }

    // 检查新增设备
    for (const sn of rcDevices) {
      if (!this.devices.has(sn)) {
        this.devices.set(sn, { sn, online: true });
        hasChanges = true;
      }
    }

    // 自动选中第一个设备
    if (rcDevices.length > 0 && !deviceContext.getCurrentDevice()) {
      deviceContext.setCurrentDevice(rcDevices[0]);
    }

    // 仅在有变化时通知
    if (hasChanges) {
      this.notify();
    }
  }

  getDevices() {
    return Array.from(this.devices.values());
  }

  remove(sn) {
    this.devices.delete(sn);
    if (deviceContext.getCurrentDevice() === sn) {
      const online = this.getDevices().find(d => d.online);
      deviceContext.setCurrentDevice(online ? online.sn : null);
    }
    this.notify();
  }

  addListener(fn) {
    this.listeners.push(fn);
  }

  notify() {
    this.listeners.forEach(fn => fn());
  }
}

export default new DeviceManager();
