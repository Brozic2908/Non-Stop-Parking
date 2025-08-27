/** @odoo-module **/
import { Component, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService, useBus } from "@web/core/utils/hooks";

export class ParkingWebSocketComponent extends Component {
  static template = "nsp_system.WebSocketComponent";
  static props = {}; // Add props definition

  setup() {
    try {
      this.busService = useService("bus_service");
      this.notificationService = useService("notification");
      this.actionService = useService("action");

      // Đăng ký channel như hospital module
      this.env.services.bus_service.addChannel("parking_log_update");
      console.log("🅿 Channel 'parking_log_update' added");

      // Subscribe đúng cách
      this.env.services.bus_service.subscribe(
        "parking_log_update",
        async (event) => {
          this.handleParkingNotification(event);
        }
      );
    } catch (error) {
      console.warn("ParkingWebSocketComponent: Services not available", error);
    }

    onMounted(() => {
      this.startListening();
    });

    onWillUnmount(() => {
      this.stopListening();
    });
  }

  startListening() {
    // Check if bus service is available before using it
    if (!this.busService) {
      console.warn("ParkingWebSocketComponent: Bus service not available");
      return;
    }

    try {
      // Đăng ký channel 'nsp_system' để khớp với Python
      this.env.services.bus_service.addChannel("nsp_system");
      console.log("🅿 Channel 'nsp_system' added");

      // Subscribe vào channel 'nsp_system'
      this.env.services.bus_service.subscribe(
        "nsp_system",
        async (notifications) => {
          console.log("📡 WebSocket notifications received:", notifications);
          for (let notification of notifications) {
            this.handleParkingNotification(notification);
          }
        }
      );
    } catch (error) {
      console.error(
        "ParkingWebSocketComponent: Error starting listener",
        error
      );
    }
  }

  stopListening() {
    if (!this.busService) {
      return;
    }

    try {
      this.busService.unsubscribe("nsp_system");
    } catch (error) {
      console.error(
        "ParkingWebSocketComponent: Error stopping listener",
        error
      );
    }
  }

  reloadCurrentView() {
    console.log("reloadCurrentView triggered, href:", window.location.href);
    // Soft reload thay vì hard reload
    // Sử dụng action service để reload view hiện tại
    if (this.actionService) {
      console.log("Reloading entire page via actionService...");
      this.actionService.doAction({
        type: "ir.actions.client",
        tag: "reload",
      });
    } else {
      console.log("No actionService — fallback to window.location.reload()");
      window.location.reload();
    }
  }

  handleParkingNotification(notification) {
    try {
      console.log("📡 WebSocket event received:", notification); // log khi có event

      const data = notification;

      if (data && data.type === "parking_log_update") {
        console.log("🚗 Parking log update from API:", data); // log dữ liệu API gửi

        // // Hiển thị toast notification
        // const direction_text = data.direction === "in" ? "Vào" : "Ra";
        // const message = `${
        //   data.vehicle_plate || "Unknown"
        // } - ${direction_text} (${data.time || "Unknown"})`;

        // if (this.notificationService) {
        //   this.notificationService.add(message, {
        //     title: "Cập nhật bãi xe",
        //     type: data.is_anomaly ? "warning" : "success",
        //     sticky: false,
        //   });
        // }
      }

      // Reload view
      this.reloadCurrentView();
    } catch (error) {
      console.error(
        "ParkingWebSocketComponent: Error handling notification",
        error
      );
    }
  }
}

// Đăng ký component với props
registry.category("main_components").add("ParkingWebSocketComponent", {
  Component: ParkingWebSocketComponent,
  props: {},
});
