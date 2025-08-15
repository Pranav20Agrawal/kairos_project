// kairos_mobile_app/lib/services/headset_service.dart
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:collection/collection.dart';

class HeadsetService {

  /// Finds and initiates a connection to a headset by its name.
  /// This is called when the PC initiates a handoff TO the phone.
  static Future<void> connectToHeadset(String headsetName) async {
    try {
      debugPrint("Attempting to connect to headset: '$headsetName'");

      if (await FlutterBluePlus.isSupported == false) {
        debugPrint("Bluetooth not supported by this device");
        return;
      }

      if (Platform.isAndroid) {
        await FlutterBluePlus.turnOn();
      }

      final connectedDevice = FlutterBluePlus.connectedDevices.firstWhereOrNull(
          (d) => d.platformName.toLowerCase() == headsetName.toLowerCase());

      if (connectedDevice != null) {
        debugPrint("Headset '$headsetName' is already connected.");
        return;
      }

      debugPrint("Starting scan for '$headsetName'...");
      BluetoothDevice? targetDevice;
      
      var scanSubscription = FlutterBluePlus.scanResults.listen((results) {
        targetDevice = results
            .firstWhereOrNull((r) =>
                r.device.platformName.toLowerCase() == headsetName.toLowerCase())
            ?.device;

        if (targetDevice != null) {
          FlutterBluePlus.stopScan();
        }
      });

      await FlutterBluePlus.startScan(timeout: const Duration(seconds: 10));
      await scanSubscription.cancel();

      if (targetDevice != null) {
        debugPrint("Found target headset: ${targetDevice!.platformName}");
        await targetDevice!.connect(timeout: const Duration(seconds: 15));
        debugPrint("Successfully initiated connection to ${targetDevice!.platformName}.");
      } else {
        debugPrint("Could not find headset '$headsetName' after scanning.");
      }
    } catch (e) {
      debugPrint("An error occurred in HeadsetService: $e");
    }
  }

  /// Finds the name of a connected Bluetooth device that is likely a headset.
  /// This is called when the phone initiates a handoff TO the PC.
  static Future<String?> findConnectedHeadsetName() async {
    try {
      if (await FlutterBluePlus.isSupported == false) {
        return null;
      }

      // The best heuristic is to find a connected device that isn't the PC itself.
      final connectedDevice = FlutterBluePlus.connectedDevices.firstWhereOrNull(
        (d) => d.platformName != "KAIROS_PC" && d.platformName.isNotEmpty,
      );

      if (connectedDevice != null) {
        debugPrint("Found connected headset: ${connectedDevice.platformName}");
        return connectedDevice.platformName;
      } else {
        debugPrint("No connected headset found (other than the PC).");
        return null;
      }
    } catch (e) {
      debugPrint("Error finding connected headset: $e");
      return null;
    }
  }
}