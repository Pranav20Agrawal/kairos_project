// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:permission_handler/permission_handler.dart'; 
import 'package:notification_listener_service/notification_listener_service.dart';

import 'package:kairos_mobile_app/theme.dart';
import 'package:kairos_mobile_app/screens/dashboard_view.dart';
import 'package:kairos_mobile_app/screens/file_transfer_view.dart';
import 'package:kairos_mobile_app/screens/settings_view.dart';
import 'package:kairos_mobile_app/screens/debug_view.dart'; // ADD THIS IMPORT
import 'package:kairos_mobile_app/services/api_service.dart';
import 'package:kairos_mobile_app/services/connection_service.dart' as connection_service;
import 'package:kairos_mobile_app/services/notification_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await NotificationService.initializeService();

  runApp(
    MultiProvider(
      providers: [
        Provider(create: (context) => ApiService()),
        ChangeNotifierProxyProvider<ApiService, connection_service.ConnectionService>(
          create: (context) => connection_service.ConnectionService(
            apiService: Provider.of<ApiService>(context, listen: false),
          ),
          update: (context, apiService, previousConnectionService) {
            // Reuse existing ConnectionService if available to prevent unnecessary recreation
            if (previousConnectionService != null) {
              return previousConnectionService;
            }
            return connection_service.ConnectionService(apiService: apiService);
          },
        ),
      ],
      child: const KairosMobileApp(),
    ),
  );
}

class KairosMobileApp extends StatelessWidget {
  const KairosMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'K.A.I.R.O.S. Mobile',
      theme: buildAppTheme(),
      debugShowCheckedModeBanner: false,
      home: const MainScreen(),
    );
  }
}

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;
  final TextEditingController _commandController = TextEditingController();

  // MODIFIED: Added DebugView to the list
  static const List<Widget> _widgetOptions = <Widget>[
    DashboardView(),
    FileTransferView(),
    SettingsView(),
    DebugView(), // ADD THIS LINE
  ];

  @override
  void initState() {
    super.initState();
    _requestPermissions();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      connection_service.ConnectionService.appContext = context;
      
      // Start the connection service after the UI is ready.
      Provider.of<connection_service.ConnectionService>(context, listen: false).start();
    });
  }

  Future<void> _requestPermissions() async {
    await [
      Permission.location,
      Permission.notification,
    ].request();
    
    bool isNotificationPermissionGranted = await NotificationListenerService.isPermissionGranted();
    if (!isNotificationPermissionGranted) {
      await NotificationListenerService.requestPermission();
    }
  }

  void _sendCommand() {
    final command = _commandController.text.trim();
    if (command.isNotEmpty) {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final connectionService = Provider.of<connection_service.ConnectionService>(context, listen: false);

      if (connectionService.isConnected && connectionService.pcIp != null) {
        apiService.sendTextCommand(command, connectionService.pcIp!);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Not connected to PC. Please wait for connection.'),
            backgroundColor: Colors.orange,
          ),
        );
      }
      
      _commandController.clear();
      FocusScope.of(context).unfocus();
    }
  }

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  void dispose() {
    _commandController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('K.A.I.R.O.S. Mobile'),
        actions: [
          Consumer<connection_service.ConnectionService>(
            builder: (context, connectionService, child) {
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Connection status indicator
                  Container(
                    width: 12,
                    height: 12,
                    margin: const EdgeInsets.only(right: 8),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _getConnectionColor(connectionService.connectionState),
                    ),
                  ),
                  // Manual reconnect button
                  if (!connectionService.isConnected)
                    IconButton(
                      icon: const Icon(Icons.refresh),
                      onPressed: connectionService.forceReconnect,
                      tooltip: 'Reconnect to PC',
                    ),
                ],
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Connection status bar
          Consumer<connection_service.ConnectionService>(
            builder: (context, connectionService, child) {
              return _buildConnectionStatusBar(connectionService);
            },
          ),
          Expanded(
            child: Center(
              child: _widgetOptions.elementAt(_selectedIndex),
            ),
          ),
        ],
      ),
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildCommandInputBar(),
          BottomNavigationBar(
            // MODIFIED: Added Debug navigation item and fixed type
            items: const <BottomNavigationBarItem>[
              BottomNavigationBarItem(
                icon: Icon(Icons.dashboard_rounded),
                label: 'Dashboard',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.swap_horiz_rounded),
                label: 'Transfer',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.settings_rounded),
                label: 'Settings',
              ),
              BottomNavigationBarItem( // ADD THIS ITEM
                icon: Icon(Icons.bug_report_rounded),
                label: 'Debug',
              ),
            ],
            currentIndex: _selectedIndex,
            onTap: _onItemTapped,
            type: BottomNavigationBarType.fixed, // ADD THIS LINE for 4+ items
          ),
        ],
      ),
    );
  }

  Widget _buildConnectionStatusBar(connection_service.ConnectionService connectionService) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      decoration: BoxDecoration(
        color: _getConnectionColor(connectionService.connectionState),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Icon(
            _getConnectionIcon(connectionService.connectionState),
            color: Colors.white,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              connectionService.statusMessage,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (connectionService.pcIp != null)
            Text(
              'PC: ${connectionService.pcIp}',
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 12,
              ),
            ),
        ],
      ),
    );
  }

  Color _getConnectionColor(connection_service.ConnectionState state) {
    switch (state) {
      case connection_service.ConnectionState.connected:
        return Colors.green;
      case connection_service.ConnectionState.connecting:
        return Colors.orange;
      case connection_service.ConnectionState.discovering:
        return Colors.blue;
      case connection_service.ConnectionState.reconnecting:
        return Colors.amber;
      case connection_service.ConnectionState.disconnected:
        return Colors.red;
    }
  }

  IconData _getConnectionIcon(connection_service.ConnectionState state) {
    switch (state) {
      case connection_service.ConnectionState.connected:
        return Icons.wifi;
      case connection_service.ConnectionState.connecting:
        return Icons.wifi_protected_setup;
      case connection_service.ConnectionState.discovering:
        return Icons.search;
      case connection_service.ConnectionState.reconnecting:
        return Icons.refresh;
      case connection_service.ConnectionState.disconnected:
        return Icons.wifi_off;
    }
  }

  Widget _buildCommandInputBar() {
    return Consumer<connection_service.ConnectionService>(
      builder: (context, connectionService, child) {
        return Material(
          elevation: 8.0,
          color: AppColors.background,
          child: Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _commandController,
                    style: const TextStyle(color: AppColors.textPrimary),
                    enabled: connectionService.isConnected,
                    decoration: InputDecoration(
                      hintText: connectionService.isConnected 
                          ? 'Type a command to PC...' 
                          : 'Waiting for PC connection...',
                      hintStyle: TextStyle(
                        color: connectionService.isConnected 
                            ? AppColors.textSecondary 
                            : Colors.grey,
                      ),
                      filled: true,
                      fillColor: connectionService.isConnected 
                          ? AppColors.card 
                          : Colors.grey.withOpacity(0.3),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 20),
                    ),
                    onSubmitted: (_) => _sendCommand(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send_rounded),
                  onPressed: connectionService.isConnected ? _sendCommand : null,
                  style: IconButton.styleFrom(
                    backgroundColor: connectionService.isConnected 
                        ? AppColors.primaryColor 
                        : Colors.grey,
                    foregroundColor: Colors.black,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}