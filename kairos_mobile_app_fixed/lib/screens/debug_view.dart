// lib/screens/debug_view.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:wifi_iot/wifi_iot.dart';
import 'package:kairos_mobile_app/services/connection_service.dart';

class DebugView extends StatefulWidget {
  const DebugView({super.key});

  @override
  State<DebugView> createState() => _DebugViewState();
}

class _DebugViewState extends State<DebugView> {
  String _currentSSID = "Unknown";
  String _ipAddress = "Unknown";
  List<WifiNetwork> _availableNetworks = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _refreshNetworkInfo();
  }

  Future<void> _refreshNetworkInfo() async {
    setState(() => _isLoading = true);
    
    try {
      final ssid = await WiFiForIoTPlugin.getSSID();
      final ip = await WiFiForIoTPlugin.getIP();
      final networks = await WiFiForIoTPlugin.loadWifiList();
      
      if (mounted) {
        setState(() {
          _currentSSID = ssid ?? "Not connected";
          _ipAddress = ip ?? "No IP";
          _availableNetworks = networks;
        });
      }
    } catch (e) {
      debugPrint("Error refreshing network info: $e");
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Connection Debug'),
      ),
      body: Consumer<ConnectionService>(
        builder: (context, connectionService, child) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildStatusCard(context, connectionService),
                const SizedBox(height: 16),
                _buildNetworkInfoCard(context),
                const SizedBox(height: 16),
                _buildAvailableNetworksCard(context),
                const SizedBox(height: 16),
                _buildDebugLogCard(context, connectionService),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildStatusCard(BuildContext context, ConnectionService cs) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Connection Status', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('State: ${cs.connectionState}'),
            Text('Status: ${cs.statusMessage}'),
            Text('PC IP: ${cs.pcIp ?? "Not detected"}'),
            const SizedBox(height: 8),
            Row(
              children: [
                ElevatedButton(
                  onPressed: cs.forceReconnect,
                  child: const Text('Force Reconnect'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () => cs.clearDebugLog(),
                  child: const Text('Clear Log'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNetworkInfoCard(BuildContext context) {
     return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Device Network Info', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('Current SSID: $_currentSSID'),
            Text('Device IP: $_ipAddress'),
            Text('Target SSID: KAIROS_LINK'),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: _isLoading ? null : _refreshNetworkInfo,
              child: _isLoading ? const Text('Refreshing...') : const Text('Refresh Network Info'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAvailableNetworksCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Visible Wi-Fi Networks', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            if (_availableNetworks.isEmpty)
              const Text('No networks found or permission denied.')
            else
              ...(_availableNetworks.take(10).map((network) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Icon(
                      network.ssid == 'KAIROS_LINK' ? Icons.computer : Icons.wifi,
                      size: 16,
                      color: network.ssid == 'KAIROS_LINK' ? Colors.green : Colors.grey,
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(network.ssid ?? 'Hidden Network')),
                    Text('${network.level} dBm'),
                  ],
                ),
              ))),
          ],
        ),
      ),
    );
  }

    Widget _buildDebugLogCard(BuildContext context, ConnectionService cs) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Connection Service Log', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Container(
              height: 300,
              width: double.infinity,
              decoration: BoxDecoration(
                color: Colors.black,
                border: Border.all(color: Colors.grey.shade700),
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                reverse: true,
                padding: const EdgeInsets.all(8),
                child: Text(
                  cs.debugLog.isEmpty ? 'No debug information yet...' : cs.debugLog,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}