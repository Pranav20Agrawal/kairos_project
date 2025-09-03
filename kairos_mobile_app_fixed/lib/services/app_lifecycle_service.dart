import 'package:flutter/material.dart';
import 'package:kairos_mobile_app/services/background_service.dart';

class AppLifecycleService with WidgetsBindingObserver {
  static final AppLifecycleService _instance = AppLifecycleService._internal();
  factory AppLifecycleService() => _instance;
  AppLifecycleService._internal();

  void initialize() {
    WidgetsBinding.instance.addObserver(this);
  }

  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    print("App lifecycle changed to: $state");
    
    switch (state) {
      case AppLifecycleState.resumed:
        // App is active - set background service to foreground for better performance
        BackgroundService.setForeground();
        break;
      case AppLifecycleState.paused:
        // App is backgrounded - ensure service continues running
        BackgroundService.setBackground();
        break;
      case AppLifecycleState.detached:
        // App is being terminated - keep background service running
        break;
      case AppLifecycleState.inactive:
        // App is transitioning - no action needed
        break;
      case AppLifecycleState.hidden:
        // App window is hidden - treat like paused
        BackgroundService.setBackground();
        break;
    }
  }
}