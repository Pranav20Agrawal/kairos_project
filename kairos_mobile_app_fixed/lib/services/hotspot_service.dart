// kairos_mobile_app/lib/services/hotspot_service.dart
import 'package:flutter/foundation.dart';
import 'package:wifi_iot/wifi_iot.dart';
import 'package:permission_handler/permission_handler.dart';

class HotspotService {
  // A method to turn on the hotspot if it's not already on.
  static Future<void> ensureHotspotOn() async {
    try {
      // For modern Android, location permission is often required for Wi-Fi tasks.
      var status = await Permission.location.request();
      if (status.isDenied) {
        debugPrint("Location permission denied. Cannot manage hotspot.");
        return;
      }

      // Check if the hotspot is already enabled
      bool? isEnabled = await WiFiForIoTPlugin.isWiFiAPEnabled();
      if (isEnabled != true) {
        debugPrint("Hotspot is not on. Attempting to enable...");
        
        // IMPORTANT: On modern Android versions (Android 10+), apps cannot
        // silently enable the hotspot. This call will likely open the system's
        // hotspot settings page for the user to manually toggle it.
        // This is a security restriction by the OS.
        // The best we can do is guide the user to the right place.
        await WiFiForIoTPlugin.setWiFiAPEnabled(true);
        debugPrint("Hotspot enable request sent. User may need to confirm in settings.");

      } else {
        debugPrint("Hotspot is already on.");
      }
    } catch (e) {
      debugPrint("Error managing hotspot: $e");
    }
  }
}