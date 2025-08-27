/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * RFID Vehicle Client Action for Vehicle Tag Assignment
 * Handles RFID tag scanning and assignment to vehicles
 */
class RFIDVehicleClientAction {
  constructor(env, params) {
    this.env = env;
    this.params = params;
    this.notification = env.services.notification;
    this.orm = env.services.orm;
  }

  /**
   * Execute the RFID vehicle client action
   * @returns {Object} Action result
   */
  async execute() {
    console.log("RFIDVehicleClientAction: Starting execution");

    const { vehicle_id, action } = this.params.params;

    if (!vehicle_id) {
      this._showError("Vehicle ID không được cung cấp");
      return this._closeAction();
    }

    if (action === "scan_and_assign_tag") {
      await this._handleScanAndAssignTag(vehicle_id);
    } else {
      this._showError("Action không được hỗ trợ");
      console.error("Unsupported action:", action);
    }

    console.log("RFIDVehicleClientAction: Execution completed");
    return this._closeAction();
  }

  /**
   * Handle scan and assign tag action
   * @param {number} vehicleId - Vehicle ID
   */
  async _handleScanAndAssignTag(vehicleId) {
    if (!this._isRFIDWidgetAvailable()) {
      this._showWarning("RFID widget chưa khởi tạo");
      return;
    }

    try {
      const tagId = await this._scanTag();
      if (!tagId) {
        console.log("No tag scanned");
        return;
      }

      console.log("Scanned tag ID for vehicle:", tagId);
      await this._assignTagToVehicle(vehicleId, tagId);
    } catch (error) {
      console.error("Error in vehicle scan and assign process:", error);
      this._showError(`Lỗi khi quét: ${error.message || error}`);
    }
  }

  /**
   * Check if RFID widget is available
   * @returns {boolean} True if widget is available
   */
  _isRFIDWidgetAvailable() {
    return typeof window !== "undefined" && window.rfidReaderWidget;
  }

  /**
   * Scan tag using RFID widget
   * @returns {Promise<string|null>} Tag ID or null
   */
  async _scanTag() {
    try {
      return await window.rfidReaderWidget.getTags();
    } catch (error) {
      console.error("Error scanning tag:", error);
      throw new Error(`Lỗi khi quét thẻ: ${error.message || error}`);
    }
  }

  /**
   * Assign tag to vehicle
   * @param {number} vehicleId - Vehicle ID
   * @param {string} tagId - Tag ID
   */
  async _assignTagToVehicle(vehicleId, tagId) {
    try {
      const result = await this.orm.call(
        "nsp.vehicle",
        "assign_tag_to_vehicle",
        [vehicleId, tagId]
      );

      this._handleAssignmentResult(result);
    } catch (error) {
      console.error("Error assigning tag to vehicle:", error);

      const errorMessage = this._extractErrorMessage(error);
      this._showError(`Lỗi khi gán thẻ: ${errorMessage}`);
    }
  }

  /**
   * Handle assignment result
   * @param {Object} result - Assignment result
   */
  _handleAssignmentResult(result) {
    if (result?.success) {
      this._showSuccess(result.message);
    } else {
      this._showWarning(result?.message || "Không thể gán thẻ");
    }
  }

  /**
   * Extract error message from error object
   * @param {Error|Object} error - Error object
   * @returns {string} Error message
   */
  _extractErrorMessage(error) {
    if (error?.message?.data?.message) {
      return error.message.data.message;
    }

    if (error?.data?.message) {
      return error.data.message;
    }

    if (error?.message) {
      return error.message;
    }

    return "Lỗi không xác định";
  }

  /**
   * Show success notification
   * @param {string} message - Success message
   */
  _showSuccess(message) {
    this.notification.add(message, { type: "success" });
  }

  /**
   * Show warning notification
   * @param {string} message - Warning message
   */
  _showWarning(message) {
    this.notification.add(message, { type: "warning" });
  }

  /**
   * Show error notification
   * @param {string} message - Error message
   */
  _showError(message) {
    this.notification.add(message, { type: "danger" });
  }

  /**
   * Close action window
   * @returns {Object} Close action
   */
  _closeAction() {
    return { type: "ir.actions.act_window_close" };
  }
}

/**
 * RFID Vehicle Client Action function wrapper for registry
 * @param {Object} env - Environment
 * @param {Object} params - Parameters
 * @returns {Promise<Object>} Action result
 */
async function RFIDVehicleClientActionWrapper(env, params) {
  const action = new RFIDVehicleClientAction(env, params);
  return await action.execute();
}

// Register the action
registry
  .category("actions")
  .add("call_rfid_reader_vehicle", RFIDVehicleClientActionWrapper);
