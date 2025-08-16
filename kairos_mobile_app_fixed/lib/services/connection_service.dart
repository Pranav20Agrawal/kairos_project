// lib/services/connection_service.dart

import 'dart:io';
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:udp/udp.dart';
import 'package:wifi_iot/wifi_iot.dart';
import 'package:kairos_mobile_app/services/api_service.dart';
import 'package:kairos_mobile_app/services/hotspot_service.dart';
import 'package:kairos_mobile_app/services/headset_service.dart';
import 'package:kairos_mobile_app/screens/pdf_viewer_screen.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:path_provider/path_provider.dart';
import 'package:kairos_mobile_app/services/notification_service.dart';

enum ConnectionState {
  disconnected,
  discovering,
  connecting,
  connected,
  reconnecting,
}

class ConnectionService extends ChangeNotifier {
  final ApiService apiService;
  WebSocketChannel? _channel;
  static BuildContext? appContext;

  ConnectionState _connectionState = ConnectionState.disconnected;
  String _statusMessage = "Initializing...";
  String? _pcIp;
  Timer? _reconnectTimer;
  Timer? _discoveryTimer;
  UDP? _udpReceiver;

  // Hotspot Credentials
  static const String KAIROS_HOTSPOT_SSID = "KAIROS_LINK";
  static const String KAIROS_HOTSPOT_PASS = "kairos1234";
  static const String KAIROS_HOTSPOT_IP = "192.168.137.1";

  // Retry logic
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const List<int> _backoffDelays = [1, 2, 3, 5, 5, 5, 5, 5, 5, 5];

  // Timeouts
  Timer? _heartbeatTimer;
  Timer? _connectionTimeoutTimer;
  static const Duration _connectionTimeout = Duration(seconds: 10);
  static const Duration _heartbeatInterval = Duration(seconds: 5);
  static const Duration _discoveryTimeout = Duration(seconds: 8);

  StreamSubscription<Map<String, dynamic>?>? _notificationSubscription;
  Timer? _clipboardTimer;
  String _lastClipboardContent = '';

  // FILE TRANSFER STATE - RACE CONDITION FIX
  File? _outputFile;
  IOSink? _fileSink;
  int _receivedBytes = 0;
  int _totalBytes = 0;
  int _handoffPageNumber = 1;
  bool _fileTransferActive = false;
  final List<List<int>> _pendingChunks = []; // Buffer for early chunks

  bool _hasTriedHotspot = false;

  // Debug logging properties
  String _debugLog = "";
  String get debugLog => _debugLog;

  void _addDebugLog(String message) {
    final timestamp = DateTime.now().toString().substring(11, 19);
    _debugLog += "[$timestamp] $message\n";
    debugPrint("ConnectionService: $message");
    notifyListeners();
  }

  void clearDebugLog() {
    _debugLog = "";
    notifyListeners();
  }

  bool get isConnected => _connectionState == ConnectionState.connected;
  ConnectionState get connectionState => _connectionState;
  String get statusMessage => _statusMessage;
  String? get pcIp => _pcIp;
  double get fileReceiveProgress =>
      _totalBytes == 0 ? 0.0 : _receivedBytes / _totalBytes;

  ConnectionService({required this.apiService}) {
    _initializeListeners();
  }

  void start() {
    _addDebugLog("ConnectionService started");
    _startConnectionProcess();
  }

  void _initializeListeners() {
    _notificationSubscription =
        NotificationService.notificationStream.listen((notification) {
      if (notification != null) {
        _sendNotificationUpdate(notification);
      }
    });

    _clipboardTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      _checkClipboard();
    });
  }

  void sendMessage(Map<String, dynamic> payload) {
    if (_channel != null && _connectionState == ConnectionState.connected) {
      try {
        final message = json.encode(payload);
        _addDebugLog("Sending message: $message");
        _channel!.sink.add(message);
      } catch (e) {
        _addDebugLog("Error sending message: $e");
        _handleDisconnect(reconnect: true);
      }
    } else {
      _addDebugLog(
          "Cannot send message - not connected. State: $_connectionState");
    }
  }

  Future<void> _startConnectionProcess() async {
    if (_connectionState == ConnectionState.connecting ||
        _connectionState == ConnectionState.connected) {
      _addDebugLog("Already connecting/connected, skipping");
      return;
    }

    await _cleanupConnections();

    if (_reconnectAttempts == 0) {
      _hasTriedHotspot = false;
    }

    _setConnectionState(ConnectionState.discovering);
    _updateStatus("Searching for KAIROS PC...");
    _addDebugLog("=== Starting Connection Process ===");

    if (!_hasTriedHotspot || _reconnectAttempts > 2) {
      await _connectToKairosHotspot();
    } else {
      await _startWiFiDiscovery();
    }
  }

  Future<void> _cleanupConnections() async {
    _addDebugLog("Cleaning up connections");
    _connectionTimeoutTimer?.cancel();
    _heartbeatTimer?.cancel();
    _discoveryTimer?.cancel();

    if (_udpReceiver != null) {
      try {
        _udpReceiver!.close();
      } catch (e) {
        _addDebugLog("Error closing UDP receiver: $e");
      }
      _udpReceiver = null;
    }

    if (_channel != null) {
      try {
        await _channel!.sink.close();
      } catch (e) {
        _addDebugLog("Error closing WebSocket: $e");
      }
      _channel = null;
    }
  }

  Future<void> _startWiFiDiscovery() async {
    if (_connectionState != ConnectionState.discovering) return;

    _addDebugLog("=== Starting WiFi Discovery ===");
    _updateStatus("Searching on current WiFi network...");

    try {
      final endpoint = Endpoint.any(port: const Port(8888));
      _udpReceiver = await UDP.bind(endpoint);
      _addDebugLog("UDP receiver bound successfully to port 8888");

      _discoveryTimer = Timer(_discoveryTimeout, () {
        _addDebugLog(
            "WiFi discovery timeout after ${_discoveryTimeout.inSeconds}s");
        if (_connectionState == ConnectionState.discovering) {
          _handleWiFiDiscoveryTimeout();
        }
      });

      _udpReceiver!.asStream().listen(
        (datagram) async {
          if (_connectionState == ConnectionState.discovering &&
              datagram != null) {
            _addDebugLog("Received UDP datagram from ${datagram.address}");
            await _processDiscoveryResponse(datagram);
          }
        },
        onError: (error) {
          _addDebugLog("UDP listen error: $error");
          if (_connectionState == ConnectionState.discovering) {
            _handleWiFiDiscoveryTimeout();
          }
        },
        cancelOnError: false,
      );
    } catch (e) {
      _addDebugLog("WiFi discovery setup error: $e");
      if (_connectionState == ConnectionState.discovering) {
        _handleWiFiDiscoveryTimeout();
      }
    }
  }

  Future<void> _processDiscoveryResponse(Datagram datagram) async {
    if (_connectionState != ConnectionState.discovering) return;

    try {
      final message = utf8.decode(datagram.data);
      _addDebugLog("Discovery message: $message");
      final data = json.decode(message);

      if (data['kairos_pc'] == true && data['ip'] != null) {
        _pcIp = data['ip'];
        _updateStatus("Found PC at $_pcIp. Connecting...");
        _addDebugLog("PC discovered at $_pcIp - attempting connection");

        _discoveryTimer?.cancel();
        await _cleanupUdp();
        await _connectToWebSocket();
      }
    } catch (e) {
      _addDebugLog("Error processing discovery response: $e");
    }
  }

  Future<void> _cleanupUdp() async {
    _discoveryTimer?.cancel();
    if (_udpReceiver != null) {
      try {
        _udpReceiver!.close();
      } catch (e) {
        _addDebugLog("Error closing UDP receiver: $e");
      }
      _udpReceiver = null;
    }
  }

  void _handleWiFiDiscoveryTimeout() {
    if (_connectionState != ConnectionState.discovering) return;
    _addDebugLog("WiFi discovery failed, trying hotspot");
    _cleanupUdp();
    _connectToKairosHotspot();
  }

  Future<void> _connectToKairosHotspot() async {
    if (_hasTriedHotspot && _reconnectAttempts < 3) {
      _addDebugLog("Already tried hotspot recently, scheduling reconnect");
      _scheduleReconnect();
      return;
    }

    _hasTriedHotspot = true;
    _setConnectionState(ConnectionState.connecting);
    _updateStatus("Connecting to KAIROS Hotspot...");
    _addDebugLog("=== Attempting Hotspot Connection ===");

    try {
      String? currentSSID = await WiFiForIoTPlugin.getSSID();
      _addDebugLog("Current SSID: ${currentSSID ?? 'null'}");

      if (currentSSID == KAIROS_HOTSPOT_SSID) {
        _addDebugLog("Already connected to KAIROS hotspot");
        _pcIp = KAIROS_HOTSPOT_IP;
        await _connectToWebSocket();
        return;
      }

      _addDebugLog("Scanning for available networks...");
      List<WifiNetwork> networks = await WiFiForIoTPlugin.loadWifiList();
      bool kairosFound =
          networks.any((network) => network.ssid == KAIROS_HOTSPOT_SSID);

      _addDebugLog(
          "Available networks: ${networks.map((n) => n.ssid).join(', ')}");
      _addDebugLog("KAIROS hotspot found in scan: $kairosFound");

      if (!kairosFound) {
        _addDebugLog(
            "KAIROS hotspot not found in scan. Trying WiFi discovery instead.");
        await _startWiFiDiscovery();
        return;
      }

      await WiFiForIoTPlugin.disconnect();
      await Future.delayed(const Duration(seconds: 1));

      bool isConnected = false;
      for (int i = 0; i < 3; i++) {
        _addDebugLog("Hotspot connection attempt ${i + 1}");
        isConnected = await WiFiForIoTPlugin.connect(
          KAIROS_HOTSPOT_SSID,
          password: KAIROS_HOTSPOT_PASS,
          security: NetworkSecurity.WPA,
        );
        if (isConnected) break;
        await Future.delayed(const Duration(seconds: 2));
      }

      _addDebugLog("Hotspot connection result: $isConnected");

      if (isConnected) {
        await Future.delayed(const Duration(seconds: 2));
        String? newSSID = await WiFiForIoTPlugin.getSSID();
        _addDebugLog("New SSID after connection: $newSSID");

        if (newSSID == KAIROS_HOTSPOT_SSID) {
          _updateStatus("Connected to Hotspot. Establishing link...");
          _pcIp = KAIROS_HOTSPOT_IP;
          await _connectToWebSocket();
        } else {
          throw Exception("SSID verification failed after connection attempt.");
        }
      } else {
        throw Exception(
            "Failed to connect to hotspot after multiple attempts.");
      }
    } catch (e) {
      _addDebugLog("Hotspot connection error: $e");
      _updateStatus("Hotspot connection failed. Retrying discovery...");
      _scheduleReconnect();
    }
  }

  Future<void> _connectToWebSocket() async {
    if (_pcIp == null) {
      _addDebugLog("No PC IP available for WebSocket connection");
      _scheduleReconnect();
      return;
    }

    _addDebugLog("=== Starting WebSocket Connection to $_pcIp ===");
    _setConnectionState(ConnectionState.connecting);
    _updateStatus("Establishing secure link...");

    _connectionTimeoutTimer = Timer(_connectionTimeout, () {
      _addDebugLog(
          "WebSocket connection timeout after ${_connectionTimeout.inSeconds}s");
      if (_connectionState == ConnectionState.connecting) {
        _handleDisconnect(reconnect: true);
      }
    });

    try {
      final wsUrl = 'ws://$_pcIp:8000/ws';
      _addDebugLog("Connecting to WebSocket: $wsUrl");

      _channel = WebSocketChannel.connect(
        Uri.parse(wsUrl),
      );

      _sendConnectionHandshake();

      _channel!.stream.listen(
        _handleIncomingMessage,
        onDone: () {
          _addDebugLog("WebSocket stream closed");
          _handleDisconnect(reconnect: true);
        },
        onError: (error) {
          _addDebugLog("WebSocket stream error: $error");
          _handleDisconnect(reconnect: true);
        },
        cancelOnError: false,
      );

      await Future.delayed(const Duration(milliseconds: 500));

      if (_connectionState == ConnectionState.connecting) {
        _addDebugLog("WebSocket connected, waiting for PC response");
      }
    } catch (e) {
      _addDebugLog("WebSocket connection error: $e");
      _handleDisconnect(reconnect: true);
    }
  }

  void _sendConnectionHandshake() {
    try {
      final handshake = {
        "type": "mobile_connect",
        "timestamp": DateTime.now().millisecondsSinceEpoch,
        "client_id": "kairos_mobile_${DateTime.now().millisecondsSinceEpoch}",
      };
      final message = json.encode(handshake);
      _addDebugLog("Sending handshake: $message");
      _channel?.sink.add(message);
    } catch (e) {
      _addDebugLog("Error sending handshake: $e");
    }
  }

  void _handleIncomingMessage(dynamic message) {
    _addDebugLog("Received message: ${message.toString()}");

    if (_connectionState == ConnectionState.connecting) {
      _addDebugLog("First message received, establishing connection");
      _establishConnection();
    }

    if (message is String) {
      try {
        final data = json.decode(message);
        final type = data['type'] as String?;
        _addDebugLog("Message type: $type");

        if (_connectionState == ConnectionState.connected) {
          _processMessage(type, data);
        }
      } catch (e) {
        _addDebugLog("Error handling JSON message: $e");
      }
    } else if (message is List<int>) {
      _addDebugLog("Received binary data chunk: ${message.length} bytes");
      if (_connectionState == ConnectionState.connected) {
        _handleFileChunk(message);
      }
    }
  }

  void _establishConnection() {
    _addDebugLog("Establishing connection");
    _connectionTimeoutTimer?.cancel();
    _setConnectionState(ConnectionState.connected);
    _reconnectAttempts = 0;
    _updateStatus("✓ Connected! Ready for symbiotic link.");

    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (timer) {
      if (_connectionState == ConnectionState.connected) {
        _sendHeartbeat();
      } else {
        timer.cancel();
      }
    });
  }

  void _sendHeartbeat() {
    try {
      sendMessage({
        "type": "heartbeat",
        "timestamp": DateTime.now().millisecondsSinceEpoch,
      });
    } catch (e) {
      _addDebugLog("Heartbeat failed: $e");
      _handleDisconnect(reconnect: true);
    }
  }

  void _processMessage(String? type, Map<String, dynamic> data) {
    _addDebugLog("Processing message type: $type");

    switch (type) {
      case 'heartbeat':
      case 'heartbeat_ack':
        _addDebugLog("Heartbeat received - connection alive");
        break;
      case 'prepare_handoff':
        _addDebugLog("Prepare handoff received");
        HotspotService.ensureHotspotOn();
        break;
      case 'clipboard_update':
        final content = data['content'] as String;
        _addDebugLog(
            "Clipboard update received: ${content.substring(0, 50)}...");
        _lastClipboardContent = content;
        Clipboard.setData(ClipboardData(text: content));
        break;
      case 'browser_handoff':
        final url = data['url'] as String?;
        _addDebugLog("Browser handoff received: $url");
        if (url != null && url.isNotEmpty) {
          launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
        }
        break;
      case 'file_start':
        _addDebugLog("File transfer start received");
        _handleFileStart(data);
        break;
      case 'file_end':
        _addDebugLog("File transfer end received");
        _handleFileEnd();
        break;
      case 'headset_handoff':
        final headsetName = data['headset_name'] as String?;
        _addDebugLog("Headset handoff received: $headsetName");
        if (headsetName != null && headsetName.isNotEmpty) {
          HeadsetService.connectToHeadset(headsetName);
        }
        break;
      default:
        _addDebugLog("Unknown message type: $type");
    }
  }

  void _handleDisconnect({bool reconnect = false}) {
    final wasConnected = _connectionState == ConnectionState.connected;
    _addDebugLog(
        "Handling disconnect. Was connected: $wasConnected, Will reconnect: $reconnect");

    _connectionTimeoutTimer?.cancel();
    _heartbeatTimer?.cancel();

    if (wasConnected || _connectionState == ConnectionState.connecting) {
      _setConnectionState(ConnectionState.disconnected);
      _updateStatus("Connection lost. Reconnecting...");
    }

    if (reconnect) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();

    if (_reconnectAttempts >= _maxReconnectAttempts) {
      _setConnectionState(ConnectionState.disconnected);
      _updateStatus("Connection failed. Tap refresh to retry.");
      _reconnectAttempts = 0;
      _hasTriedHotspot = false;
      return;
    }

    final delayIndex = _reconnectAttempts.clamp(0, _backoffDelays.length - 1);
    final delay = _backoffDelays[delayIndex];

    _setConnectionState(ConnectionState.reconnecting);
    _updateStatus(
        "Reconnecting... (${_reconnectAttempts + 1}/$_maxReconnectAttempts)");

    _reconnectAttempts++;
    _addDebugLog(
        "Scheduling reconnect in ${delay}s (attempt $_reconnectAttempts)");

    _reconnectTimer = Timer(Duration(seconds: delay), () {
      if (_connectionState == ConnectionState.reconnecting) {
        _addDebugLog("Executing scheduled reconnect");
        _startConnectionProcess();
      }
    });
  }

  void _setConnectionState(ConnectionState newState) {
    if (_connectionState != newState) {
      _addDebugLog("Connection state changed: $_connectionState -> $newState");
      _connectionState = newState;
      notifyListeners();
    }
  }

  Future<void> forceReconnect() async {
    _addDebugLog("Force reconnect triggered");
    _reconnectAttempts = 0;
    _hasTriedHotspot = false;
    await _startConnectionProcess();
  }

  // RACE CONDITION FIX: Proper async file initialization with buffering
  Future<void> _handleFileStart(Map<String, dynamic> data) async {
    // Reset all file transfer state at the beginning
    _fileTransferActive = true;
    _receivedBytes = 0;
    _totalBytes = 0;
    _outputFile = null;
    _fileSink = null;
    _pendingChunks.clear();

    final fileName = data['file_name'] as String?;
    final fileSize = data['file_size'] as int?;
    _handoffPageNumber = data['page_number'] as int? ?? 1;

    if (fileName == null || fileSize == null) {
      _addDebugLog("Error: Invalid file_start message. Missing name or size.");
      _fileTransferActive = false;
      return;
    }

    _totalBytes = fileSize;
    _addDebugLog(
        "File transfer initiated: $fileName ($_totalBytes bytes, page $_handoffPageNumber)");
    _updateStatus("Receiving file: $fileName...");
    notifyListeners();

    try {
      final tempDir = await getTemporaryDirectory();
      _outputFile = File('${tempDir.path}/$fileName');

      if (await _outputFile!.exists()) {
        await _outputFile!.delete();
      }

      // Open the sink and ONLY THEN process any buffered chunks
      _fileSink = _outputFile!.openWrite();
      _addDebugLog("File sink is ready. Processing ${_pendingChunks.length} buffered chunks.");

      // Critical change: Process buffered chunks only after the sink is open
      for (final chunk in _pendingChunks) {
        _fileSink?.add(chunk);
        _receivedBytes += chunk.length;
      }
      _pendingChunks.clear();
      notifyListeners(); // Update UI with progress from buffered chunks

    } catch (e) {
      _addDebugLog("Error during file start/initialization: $e");
      _fileTransferActive = false;
      _fileSink?.close();
    }
  }

  // RACE CONDITION FIX: Safe chunk handling with buffering
  void _handleFileChunk(List<int> chunk) {
    if (!_fileTransferActive) {
      _addDebugLog("Chunk received but transfer not active. Discarding.");
      return;
    }

    // If the sink isn't ready, buffer the chunk and wait.
    if (_fileSink == null) {
      _addDebugLog("Sink not ready. Buffering chunk (${chunk.length} bytes).");
      _pendingChunks.add(chunk);
      return;
    }

    // If sink is ready, write the chunk directly.
    _fileSink?.add(chunk);
    _receivedBytes += chunk.length;
    final progress = (_receivedBytes / _totalBytes * 100).toStringAsFixed(0);
    _updateStatus("Receiving file... $progress%");
    notifyListeners();
  }

  void _writeSingleChunk(List<int> chunk) {
    try {
      _fileSink!.add(chunk);
      _receivedBytes += chunk.length;
      
      if (_totalBytes > 0) {
        final progress = (_receivedBytes / _totalBytes * 100).toStringAsFixed(0);
        _addDebugLog(
            "Received chunk: ${chunk.length} bytes, total: $_receivedBytes/$_totalBytes ($progress%)");
        _updateStatus("Receiving file... $progress%");
        notifyListeners();
      }
    } catch (e) {
      _addDebugLog("Error writing chunk: $e");
    }
  }

  Future<void> _handleFileEnd() async {
    if (!_fileTransferActive) {
      _addDebugLog("File end received but transfer not active.");
      return;
    }

    _addDebugLog("File transfer finished. Closing file sink.");

    await _fileSink?.flush();
    await _fileSink?.close();
    
    _updateStatus("File received successfully. Opening...");
    notifyListeners();

    if (_outputFile != null && await _outputFile!.exists() && appContext != null) {
      _addDebugLog("Navigating to PDF viewer for ${_outputFile!.path}");
      Navigator.push(
        appContext!,
        MaterialPageRoute(
          builder: (context) => PdfViewerScreen(
            filePath: _outputFile!.path,
            initialPage: _handoffPageNumber,
          ),
        ),
      );
    } else {
      _addDebugLog("Failed to open file. Path: ${_outputFile?.path}, Exists: ${await _outputFile?.exists()}, Context: $appContext");
    }

    // Reset state for the next transfer
    _fileTransferActive = false;
  }

  Future<void> _checkClipboard() async {
    if (_connectionState != ConnectionState.connected) return;
    try {
      ClipboardData? data = await Clipboard.getData(Clipboard.kTextPlain);
      String? text = data?.text;
      if (text != null && text.isNotEmpty && text != _lastClipboardContent) {
        _lastClipboardContent = text;
        _sendClipboardUpdate(text);
      }
    } catch (e) {
      _addDebugLog("Error checking clipboard: $e");
    }
  }

  void _sendClipboardUpdate(String text) {
    _addDebugLog("Sending clipboard update: ${text.substring(0, 50)}...");
    sendMessage({"type": "clipboard_update", "content": text});
  }

  void _sendNotificationUpdate(Map<String, dynamic> notification) {
    _addDebugLog("Sending notification update: ${notification['title']}");
    sendMessage({
      "type": "notification_update",
      "title": notification['title'],
      "content": notification['content'],
      "package_name": notification['package_name'],
    });
  }

  void _updateStatus(String message) {
    _addDebugLog("Status update: $message");
    _statusMessage = message;
    notifyListeners();
  }

  @override
  void dispose() {
    _addDebugLog("ConnectionService disposing");
    _reconnectTimer?.cancel();
    _discoveryTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    _heartbeatTimer?.cancel();
    _clipboardTimer?.cancel();
    _notificationSubscription?.cancel();

    _cleanupConnections().then((_) {
      super.dispose();
    });
  }
}