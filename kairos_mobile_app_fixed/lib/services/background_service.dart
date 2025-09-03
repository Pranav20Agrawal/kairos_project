import 'dart:async';
import 'dart:ui';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_background_service_android/flutter_background_service_android.dart';

@pragma("vm:entry-point")
void onStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();

  String lastClipboardContent = '';
  Timer? clipboardTimer;
  bool isRunning = true;

  // Enhanced clipboard checking with better error handling
  void checkClipboard(Timer timer) async {
    if (!isRunning) {
      timer.cancel();
      return;
    }

    if (service is AndroidServiceInstance) {
      if (!await service.isForegroundService()) {
        // If not foreground, still check but less frequently
        if (timer.tick % 3 != 0) return; // Check every 3rd time (every 3 seconds)
      }
    }

    try {
      final clipboardData = await Clipboard.getData(Clipboard.kTextPlain);
      final text = clipboardData?.text;
      
      if (text != null && text.isNotEmpty && text.trim() != lastClipboardContent.trim()) {
        lastClipboardContent = text;
        print("Background service: Clipboard changed to: ${text.length > 50 ? text.substring(0, 50) + '...' : text}");
        
        // Send to main app
        service.invoke('clipboard_update', {
          'content': text,
          'timestamp': DateTime.now().millisecondsSinceEpoch,
        });
      }
    } catch (e) {
      print("Background service: Error reading clipboard: $e");
      // Continue running even if clipboard read fails
    }
  }

  // Android-specific service management
  if (service is AndroidServiceInstance) {
    service.on('setAsForeground').listen((event) {
      print("Background service: Setting as foreground");
      service.setAsForegroundService();
      // Restart timer with higher frequency when foreground
      clipboardTimer?.cancel();
      clipboardTimer = Timer.periodic(const Duration(seconds: 1), checkClipboard);
    });

    service.on('setAsBackground').listen((event) {
      print("Background service: Setting as background");
      service.setAsBackgroundService();
      // Continue but with lower frequency
      clipboardTimer?.cancel();
      clipboardTimer = Timer.periodic(const Duration(seconds: 2), checkClipboard);
    });
  }

  service.on('stopService').listen((event) {
    print("Background service: Stop requested");
    isRunning = false;
    clipboardTimer?.cancel();
    service.stopSelf();
  });

  // Start the clipboard monitoring
  print("Background service: Starting clipboard monitor");
  clipboardTimer = Timer.periodic(const Duration(seconds: 1), checkClipboard);
  
  // Initial clipboard read to establish baseline
  try {
    final initialData = await Clipboard.getData(Clipboard.kTextPlain);
    if (initialData?.text != null) {
      lastClipboardContent = initialData!.text!;
      print("Background service: Initial clipboard content cached (${lastClipboardContent.length} chars)");
    }
  } catch (e) {
    print("Background service: Could not read initial clipboard: $e");
  }
}

class BackgroundService {
  static final FlutterBackgroundService _service = FlutterBackgroundService();
  static bool _isInitialized = false;

  static Future<void> initializeService() async {
    if (_isInitialized || !Platform.isAndroid) return;
    
    try {
      await _service.configure(
        iosConfiguration: IosConfiguration(),
        androidConfiguration: AndroidConfiguration(
          onStart: onStart,
          isForegroundMode: true,
          autoStart: true,
          autoStartOnBoot: true,
          notificationChannelId: 'kairos_service',
          initialNotificationTitle: 'K.A.I.R.O.S. Link Active',
          initialNotificationContent: 'Clipboard sync is running in background.',
          foregroundServiceNotificationId: 888,
        ),
      );
      _isInitialized = true;
      print("Background service initialized successfully");
    } catch (e) {
      print("Failed to initialize background service: $e");
    }
  }

  static Stream<Map<String, dynamic>?> get clipboardStream {
    return _service.on('clipboard_update');
  }

  static Future<void> setForeground() async {
    _service.invoke('setAsForeground');
  }

  static Future<void> setBackground() async {
    _service.invoke('setAsBackground');
  }

  static Future<void> stop() async {
    _service.invoke('stopService');
  }

  static Future<bool> isRunning() async {
    return await _service.isRunning();
  }
}