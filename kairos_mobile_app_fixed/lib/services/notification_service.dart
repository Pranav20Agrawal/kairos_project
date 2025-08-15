// kairos_mobile_app/lib/services/notification_service.dart
import 'dart:async';
import 'dart:ui';
import 'dart:io'; // <-- THIS LINE WAS CORRECTED
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:notification_listener_service/notification_listener_service.dart';

@pragma("vm:entry-point")
void onStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();
  
  if (service is AndroidServiceInstance) {
    service.on('setAsForeground').listen((event) {
      service.setAsForegroundService();
    });

    service.on('setAsBackground').listen((event) {
      service.setAsBackgroundService();
    });
  }

  NotificationListenerService.notificationsStream.listen((event) {
    service.invoke('new_notification', {
      "title": event.title,
      "content": event.content,
      "package_name": event.packageName,
    });
  });
}

class NotificationService {
  static final FlutterBackgroundService _service = FlutterBackgroundService();

  static Future<void> initializeService() async {
    if (Platform.isAndroid) {
        await _service.configure(
        iosConfiguration: IosConfiguration(),
        androidConfiguration: AndroidConfiguration(
          onStart: onStart,
          isForegroundMode: true,
          autoStart: true,
          autoStartOnBoot: true,
        ),
      );
    }
  }

  static Future<void> requestPermission() async {
    bool isPermissionGranted = await NotificationListenerService.isPermissionGranted();
    if (!isPermissionGranted) {
      await NotificationListenerService.requestPermission();
    }
  }

  static Stream<Map<String, dynamic>?> get notificationStream {
    return _service.on('new_notification').map((event) => event);
  }
}