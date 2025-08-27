/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";

export class ParkingListController extends ListController {
  setup() {
    super.setup();

    this.busService = useService("bus_service");

    onMounted(() => {
      console.log(
        "🅿 ParkingListController mounted — subscribing to 'nsp_system'"
      );
      try {
        this.busService.subscribe("nsp_system", (notifications) => {
          console.log("🔔 Received notifications:", notifications);
          for (let notification of notifications) {
            console.log("➡ Processing notification:", notification);
            if (notification.type === "parking_log_update") {
              if (this.model) {
                console.log("* Action: reloading model data *");
                this.model
                  .load()
                  .then(() => console.log("✅ Model loaded successfully"))
                  .catch((err) =>
                    console.error("❌ Error loading model:", err)
                  );
              } else {
                console.warn("⚠ Model not ready yet, skip reload");
              }
            }
          }
        });
      } catch (error) {
        console.error("❌ Error subscribing to 'nsp_system':", error);
      }
    });

    onWillUnmount(() => {
      console.log("🅿 ParkingListController unmounted — unsubscribing");
      this.busService.unsubscribe("nsp_system");
    });
  }
}

import { registry } from "@web/core/registry";
registry.category("views").add("parking_logs_list", {
  ...registry.category("views").get("list"),
  Controller: ParkingListController,
});
