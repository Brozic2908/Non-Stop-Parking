/** @odoo-module **/

import { Component, useState, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * RFID Reader Widget for Odoo 18
 * Manages RFID reader connections and tag scanning
 */
export class RFIDReaderWidget extends Component {
  static template = "non_stop_parking.RFIDReaderWidget";

  setup() {
    // Services
    this.orm = useService("orm");
    this.notification = useService("notification");
    this.action = useService("action");

    // Constants
    this.STORAGE_KEY = "rfid_reader_device";
    this.API_TIMEOUT = 5000;
    this.DISCOVERY_TIMEOUT = 100;
    this.CONCURRENCY_LIMIT = 25;
    this.PORT_RANGE = { start: 10000, end: 11000 };
    // this.LOCALHOST = "localhost";
    this.LOCALHOST = "127.0.0.1";

    // Flags
    this._isAutoConnecting = false;
    this._isDestroyed = false;

    // State management
    this.state = useState({
      // Connection states
      isConnected: false,
      connectionStatus: "disconnected", // disconnected, connecting, connected
      readerInfo: null,
      isScanning: false,

      // Modal states
      showDeviceModal: false,
      availableDevices: [],
      isDiscovering: false,
      testingDevice: null,

      // Configuration modal
      showConfigModal: false,
      configDevice: null,
    });

    // Register global widget reference
    this._registerGlobalWidget();

    // Auto-connect to saved device
    this._autoConnectSavedDevice();

    // Cleanup on destroy
    onWillDestroy(() => {
      this._isDestroyed = true;
      this._unregisterGlobalWidget();
    });
  }

  // ===========================================
  // LIFECYCLE METHODS
  // ===========================================

  /**
   * Register widget globally for external access
   * @private
   */
  _registerGlobalWidget() {
    if (typeof window !== "undefined") {
      window.rfidReaderWidget = this;
    }
  }

  /**
   * Unregister global widget reference
   * @private
   */
  _unregisterGlobalWidget() {
    if (typeof window !== "undefined" && window.rfidReaderWidget === this) {
      delete window.rfidReaderWidget;
    }
  }

  // ===========================================
  // STORAGE MANAGEMENT
  // ===========================================

  /**
   * Save device information to localStorage
   * @param {Object} readerInfo - Reader information
   */
  _saveDeviceToStorage(readerInfo) {
    if (!readerInfo?.readerId || !readerInfo?.comPort) {
      console.warn("Cannot save incomplete device info:", readerInfo);
      return;
    }

    try {
      const deviceData = {
        host: readerInfo.host,
        port: readerInfo.port,
        readerId: readerInfo.readerId,
        comPort: readerInfo.comPort,
        readerName: readerInfo.readerName,
        lastConnected: new Date().toISOString(),
      };

      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(deviceData));
      console.log("Device saved to localStorage:", deviceData);
    } catch (error) {
      console.error("Error saving device to localStorage:", error);
    }
  }

  /**
   * Get device information from localStorage
   * @returns {Object|null} Saved device data
   */
  _getDeviceFromStorage() {
    try {
      const deviceData = localStorage.getItem(this.STORAGE_KEY);
      if (deviceData) {
        const parsed = JSON.parse(deviceData);
        console.log("Device loaded from localStorage:", parsed);
        return parsed;
      }
    } catch (error) {
      console.error("Error loading device from localStorage:", error);
    }
    return null;
  }

  /**
   * Remove device information from localStorage
   */
  _removeDeviceFromStorage() {
    try {
      localStorage.removeItem(this.STORAGE_KEY);
      console.log("Device removed from localStorage");
    } catch (error) {
      console.error("Error removing device from localStorage:", error);
    }
  }

  // ===========================================
  // CONNECTION MANAGEMENT
  // ===========================================

  /**
   * Auto-connect to saved device on initialization
   * @private
   */
  async _autoConnectSavedDevice() {
    if (this._isAutoConnecting || this._isDestroyed) {
      return;
    }

    this._isAutoConnecting = true;

    try {
      const savedDevice = this._getDeviceFromStorage();
      if (!savedDevice) {
        return;
      }

      this.state.connectionStatus = "connecting";

      // Validate saved device
      const validatedDevice = await this._validateSavedDevice(savedDevice);
      if (!validatedDevice) {
        this._removeDeviceFromStorage();
        this.state.connectionStatus = "disconnected";
        this._showNotification(
          "Thiết bị đã lưu không khả dụng. Vui lòng kết nối lại.",
          "warning"
        );
        return;
      }

      // Check if reader exists in system
      const isValidReader = await this._validateReaderInSystem(
        validatedDevice.readerId
      );
      if (!isValidReader) {
        this._removeDeviceFromStorage();
        this.state.connectionStatus = "disconnected";
        this._showNotification(
          `Thiết bị ${validatedDevice.readerId} chưa được đăng ký trong hệ thống. Hãy liên hệ chúng tôi để được hỗ trợ.`,
          "warning",
          true
        );
        return;
      }

      // Connect to validated device
      await this._connectToValidatedDevice(validatedDevice, savedDevice);
    } catch (error) {
      console.error("Error in auto-connect:", error);
      this.state.connectionStatus = "disconnected";
      this._showNotification(
        `Lỗi khi tự động kết nối: ${error.message}`,
        "danger"
      );
    } finally {
      this._isAutoConnecting = false;
    }
  }

  /**
   * Connect to a validated device
   * @private
   */
  async _connectToValidatedDevice(validatedDevice, savedDevice) {
    this.state.readerInfo = {
      readerId: validatedDevice.readerId,
      comPort: validatedDevice.comPort,
      host: savedDevice.host,
      port: savedDevice.port,
      status: validatedDevice.status || "active",
      readerName: validatedDevice.readerName || savedDevice.readerName,
    };

    this.state.isConnected = true;
    this.state.connectionStatus = "connected";

    this._saveDeviceToStorage(this.state.readerInfo);

    console.log("Auto-connected to device:", this.state.readerInfo);
  }

  /**
   * Validate saved device against current available devices
   * @param {Object} deviceInfo - Saved device information
   * @returns {Object|null} Validated device or null
   */
  async _validateSavedDevice(deviceInfo) {
    try {
      const readers = await this._getReaderList(
        deviceInfo.host,
        deviceInfo.port
      );
      return readers.find(
        (r) =>
          r.readerId === deviceInfo.readerId && r.comPort === deviceInfo.comPort
      );
    } catch (error) {
      console.error("Error validating saved device:", error);
      return null;
    }
  }

  /**
   * Check if reader exists in Odoo system
   * @param {string} readerId - Reader ID to validate
   * @returns {boolean} True if reader exists
   */
  async _validateReaderInSystem(readerId) {
    try {
      const result = await this.orm.searchCount("nsp.reader", [
        ["reader_id", "=", readerId],
      ]);
      return result > 0;
    } catch (error) {
      console.error("Error validating reader in system:", error);
      return false;
    }
  }

  // ===========================================
  // API COMMUNICATION
  // ===========================================

  /**
   * Call discovery API to check for Reader Service
   * @param {string} host - Host address
   * @param {number} port - Port number
   * @param {number} timeout - Request timeout
   * @returns {boolean} True if discovery successful
   */
  async _callDiscoveryAPI(host, port, timeout = this.DISCOVERY_TIMEOUT) {
    try {
      const response = await fetch(`http://${host}:${port}/api/v1/Discover`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ Key: "nonestopparkingxinchao" }),
        signal: AbortSignal.timeout(timeout),
      });

      if (response.ok) {
        const data = await response.json();
        return data.Success && data.Message === "DISCOVER SERVICE SUCCESSFULLY";
      }
    } catch (error) {
      // Silent fail for discovery to reduce noise
      return false;
    }
    return false;
  }

  /**
   * Get reader list from API
   * @param {string} host - Host address
   * @param {number} port - Port number
   * @returns {Array} List of readers
   */
  async _getReaderList(host, port) {
    try {
      const response = await fetch(`http://${host}:${port}/api/v1/GetDevices`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        signal: AbortSignal.timeout(2000),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.Success && Array.isArray(data.Data)) {
          // Chuẩn hóa lại cho giống code cũ
          return data.Data.map((d) => ({
            readerId: d.DeviceId,
            comPort: d.ComPort,
            readerName: d.DeviceName,
          }));
        }
      }
    } catch (error) {
      console.warn(
        `Cannot get device list from ${host}:${port} - ${error.message}`
      );
    }
    return [];
  }

  /**
   * Gọi API [POST] /api/v1/SetDevice để chọn thiết bị
   * @param {string} host
   * @param {number} port
   * @param {string} comPort
   * @returns {Promise<Object>} Thông tin thiết bị đã set
   */
  async _setDevice(host, port, comPort) {
    const response = await fetch(`http://${host}:${port}/api/v1/SetDevice`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // "Authorization": "Token abc123securetoken", // nếu cần
      },
      body: JSON.stringify({ ComPort: comPort }),
      signal: AbortSignal.timeout(this.API_TIMEOUT),
    });
    const data = await response.json();
    if (!data.Success) {
      throw new Error(data.Message || "Không thể chọn thiết bị");
    }
    return data.Data;
  }

  // ===========================================
  // DEVICE DISCOVERY
  // ===========================================

  /**
   * Discover available RFID devices
   * @returns {Array} List of discovered devices
   */
  async discoverDevices() {
    const taskFns = [];

    // Create discovery tasks for port range
    for (
      let port = this.PORT_RANGE.start;
      port <= this.PORT_RANGE.end;
      port++
    ) {
      const currentPort = port;
      taskFns.push(async () => {
        const discoveryResult = await this._callDiscoveryAPI(
          this.LOCALHOST,
          currentPort
        );
        return discoveryResult
          ? { host: this.LOCALHOST, port: currentPort }
          : null;
      });
    }

    // Run discovery with concurrency limit
    const discoveryResults = await this._runWithConcurrencyLimit(
      taskFns,
      this.CONCURRENCY_LIMIT
    );
    const validPorts = discoveryResults.filter((result) => result !== null);

    // Get detailed reader information
    const allDevices = [];
    for (const portInfo of validPorts) {
      const readerList = await this._getReaderList(
        portInfo.host,
        portInfo.port
      );

      for (const reader of readerList) {
        const isValidReader = await this._validateReaderInSystem(
          reader.readerId
        );

        allDevices.push({
          readerId: reader.readerId,
          comPort: reader.comPort,
          host: portInfo.host,
          port: portInfo.port,
          isRegisteredInSystem: isValidReader,
        });
      }
    }

    return allDevices;
  }

  /**
   * Run tasks with concurrency limit
   * @param {Array} taskFns - Array of task functions
   * @param {number} limit - Concurrency limit
   * @returns {Array} Results array
   */
  async _runWithConcurrencyLimit(taskFns, limit = 5) {
    const results = [];
    let i = 0;

    const run = async () => {
      while (i < taskFns.length) {
        const current = i++;
        try {
          const taskWithTimeout = Promise.race([
            taskFns[current](),
            new Promise((_, reject) =>
              setTimeout(() => reject(new Error("Task timeout")), 3000)
            ),
          ]);
          results[current] = await taskWithTimeout;
        } catch (error) {
          results[current] = null;
        }
      }
    };

    const workers = Array.from(
      { length: Math.min(limit, taskFns.length) },
      run
    );

    await Promise.all(workers);
    return results;
  }

  // ===========================================
  // USER INTERFACE METHODS
  // ===========================================

  /**
   * Show device selection modal
   */
  async showDeviceSelectionModal() {
    this.state.showDeviceModal = true;
    this.state.isDiscovering = true;
    this.state.availableDevices = [];

    try {
      const devices = await this.discoverDevices();
      this.state.availableDevices = devices;

      if (devices.length === 0) {
        this._showNotification(
          "Không tìm thấy thiết bị nào. Hãy đảm bảo service đang chạy trên localhost.",
          "warning"
        );
      }
    } catch (error) {
      this._showNotification(
        `Lỗi khi tìm kiếm thiết bị: ${error.message}`,
        "danger"
      );
    } finally {
      this.state.isDiscovering = false;
    }
  }

  /**
   * Close device selection modal
   */
  closeDeviceModal() {
    this.state.showDeviceModal = false;
    this.state.availableDevices = [];
    this.state.testingDevice = null;
  }

  /**
   * Close configuration modal
   */
  closeConfigModal() {
    this.state.showConfigModal = false;
    this.state.configDevice = null;
  }

  /**
   * Test device connection
   * @param {Object} device - Device to test
   */
  async testDevice(device) {
    this.state.testingDevice = device.readerId;

    try {
      const response = await fetch(
        `http://${device.host}:${device.port}/api/v1/TestDevice`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ ComPort: device.comPort }),
          signal: AbortSignal.timeout(3000),
        }
      );

      const data = await response.json();
      if (data.Success) {
        this._showNotification(
          `Test thành công cho ${device.readerId} (${device.comPort}).`,
          "success"
        );
      } else {
        throw new Error(data.Message || "Test thất bại");
      }
    } catch (error) {
      this._showNotification(
        `Test thất bại cho ${device.readerId}: ${error.message}`,
        "warning"
      );
    } finally {
      this.state.testingDevice = null;
    }
  }

  /**
   * Show device configuration
   * @param {Object} device - Device to configure
   */
  async showDeviceConfig(device) {
    if (!device.isRegisteredInSystem) {
      this._showNotification(
        `Reader ID: ${device.readerId} chưa được đăng ký. Không thể cấu hình.`,
        "warning"
      );
      return;
    }

    try {
      const readerIds = await this.orm.search("nsp.reader", [
        ["reader_id", "=", device.readerId],
      ]);

      if (readerIds.length > 0) {
        this.action.doAction({
          type: "ir.actions.act_window",
          name: `Cấu hình ${device.readerId}`,
          res_model: "nsp.reader",
          res_id: readerIds[0],
          view_mode: "form",
          views: [[false, "form"]],
          target: "new",
          context: {
            default_reader_id: device.readerId,
            default_ip_address: device.host,
            default_port: device.port,
            default_com_port: device.comPort,
          },
        });
      } else {
        this._showNotification(
          `Thiết bị ${device.readerId} chưa được hỗ trợ. Hãy liên hệ với chúng tôi để được hỗ trợ.`,
          "warning"
        );
      }
    } catch (error) {
      this._showNotification(`Lỗi khi mở cấu hình: ${error.message}`, "danger");
    }
  }

  /**
   * Select and connect to device
   * @param {Object} device - Device to connect
   */
  async selectDevice(device) {
    // Do not select if the device is not registered.
    if (!device.isRegisteredInSystem) {
      this.notification.add(
        `Reader ID ${device.readerId} chưa được đăng ký trong hệ thống. Không thể kết nối.`,
        { type: "warning" }
      );
      return;
    }

    // Check if already connected to this device
    if (this._isCurrentDevice(device)) {
      this._showNotification(
        `Thiết bị ${device.readerName} (${device.comPort}) đã được kết nối.`,
        "info"
      );
      this.closeDeviceModal();
      return;
    }

    // Disconnect from current device if connected
    if (this.state.isConnected) {
      this.disconnectFromReader();
    }

    this.state.connectionStatus = "connecting";

    try {
      // Gọi SetDevice trước khi test kết nối
      await this._setDevice(device.host, device.port, device.comPort);

      // Sau khi set thành công, test kết nối (nếu muốn)
      await this._connectToDevice(device);

      // Đóng modal sau khi kết nối thành công
      this.closeDeviceModal();
    } catch (error) {
      this.state.connectionStatus = "disconnected";
      this._showNotification(`Lỗi kết nối: ${error.message}`, "danger");
    }
  }

  /**
   * Check if device is currently connected
   * @param {Object} device - Device to check
   * @returns {boolean} True if currently connected
   */
  _isCurrentDevice(device) {
    return (
      this.state.readerInfo &&
      this.state.readerInfo.readerId === device.readerId &&
      this.state.readerInfo.comPort === device.comPort
    );
  }

  /**
   * Connect to specific device
   * @param {Object} device - Device to connect
   */
  async _connectToDevice(device) {
    // Gọi TestDevice để kiểm tra kết nối
    // const response = await fetch(
    //   `http://${device.host}:${device.port}/api/v1/TestDevice`,
    //   {
    //     method: "POST",
    //     headers: {
    //       "Content-Type": "application/json",
    //     },
    //     body: JSON.stringify({ ComPort: device.comPort }),
    //     signal: AbortSignal.timeout(this.API_TIMEOUT),
    //   }
    // );

    // if (!response.ok) {
    //   throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    // }

    // const data = await response.json();
    // if (!data.Success) {
    //   throw new Error(data.Message || "Không thể chọn thiết bị");
    // }

    // Update state
    this.state.readerInfo = {
      readerId: device.readerId,
      comPort: device.comPort,
      host: device.host,
      port: device.port,
      readerName: device.readerName,
    };

    this.state.isConnected = true;
    this.state.connectionStatus = "connected";

    // Save to storage
    this._saveDeviceToStorage(this.state.readerInfo);

    this._showNotification(
      `Kết nối thành công với Reader ${device.readerName} - ${device.readerId} (${device.comPort}) tại ${device.host}:${device.port}`,
      "success"
    );
  }

  /**
   * Connect to reader (show device selection)
   */
  async connectToReader() {
    await this.showDeviceSelectionModal();
  }

  /**
   * Change current device
   */
  async changeDevice() {
    await this.showDeviceSelectionModal();
  }

  /**
   * Disconnect from current reader
   */
  disconnectFromReader() {
    const readerName = this.state.readerInfo?.readerId || "Unknown";

    this.state.isConnected = false;
    this.state.readerInfo = null;
    this.state.connectionStatus = "disconnected";
    this.state.isScanning = false;

    this._removeDeviceFromStorage();

    this._showNotification(`Đã ngắt kết nối với Reader ${readerName}`, "info");
  }

  // ===========================================
  // TAG SCANNING
  // ===========================================

  /**
   * Get tags from connected reader
   * @returns {string|null} Tag ID or null
   */
  async getTags() {
    if (!this.state.isConnected || !this.state.readerInfo) {
      this._showNotification("Chưa kết nối với Reader Service", "warning");
      return null;
    }
    this.state.isScanning = true;
    try {
      const response = await fetch(
        `http://${this.state.readerInfo.host}:${this.state.readerInfo.port}/api/v1/read`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          signal: AbortSignal.timeout(this.API_TIMEOUT),
        }
      );
      const data = await response.json();
      if (!data.Success) {
        throw new Error(data.Message || "Lỗi không xác định");
      }
      if (Array.isArray(data.Data) && data.Data.length >= 2) {
        this._showNotification(
          "Phát hiện 2 thẻ cùng lúc. Vui lòng chỉ quét một thẻ tại một thời điểm.",
          "warning"
        );
        return null;
      }
      if (Array.isArray(data.Data) && data.Data.length > 0) {
        return data.Data[0].UID;
      } else {
        this._showNotification("Không phát hiện thẻ nào", "info");
        return null;
      }
    } catch (error) {
      this._handleScanError(error);
      return null;
    } finally {
      this.state.isScanning = false;
    }
  }

  /**
   * Handle scan errors
   * @param {Error} error - Error object
   */
  _handleScanError(error) {
    let message = `Lỗi khi lấy thẻ: ${error.message}`;
    let type = "danger";

    if (error.name === "AbortError") {
      message = "Timeout khi lấy thẻ";
      type = "warning";
    } else if (error.name === "TypeError") {
      message = "Lỗi kết nối mạng";
    }

    this._showNotification(message, type);
  }

  // ===========================================
  // UTILITY METHODS
  // ===========================================

  /**
   * Show notification
   * @param {string} message - Notification message
   * @param {string} type - Notification type
   * @param {boolean} sticky - Whether notification is sticky
   */
  _showNotification(message, type = "info", sticky = false) {
    const options = { type };
    if (sticky) {
      options.sticky = true;
    }
    this.notification.add(message, options);
  }

  // ===========================================
  // COMPUTED PROPERTIES
  // ===========================================

  /**
   * Get connection button text based on status
   */
  get connectionButtonText() {
    switch (this.state.connectionStatus) {
      case "connecting":
        return "Đang kết nối...";
      case "connected":
        return "Ngắt kết nối";
      default:
        return "Kết nối Reader";
    }
  }

  /**
   * Get connection button CSS class based on status
   */
  get connectionButtonClass() {
    switch (this.state.connectionStatus) {
      case "connecting":
        return "btn-warning";
      case "connected":
        return "btn-danger";
      default:
        return "btn-primary";
    }
  }

  /**
   * Check if has saved device
   */
  get hasSavedDevice() {
    return this._getDeviceFromStorage() !== null;
  }
}

// Register widget
registry.category("view_widgets").add("rfid_reader", {
  component: RFIDReaderWidget,
});

export default RFIDReaderWidget;
