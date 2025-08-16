// lib/screens/debug_view.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:kairos_mobile_app/services/connection_service.dart' as connection_service;

class DebugView extends StatefulWidget {
  const DebugView({super.key});

  @override
  State<DebugView> createState() => _DebugViewState();
}

class _DebugViewState extends State<DebugView> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Consumer<connection_service.ConnectionService>(
        builder: (context, connectionService, child) {
          return Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Connection Status Card
                _buildStatusCard(connectionService),
                const SizedBox(height: 16),
                
                // File Transfer Status Card
                _buildFileTransferCard(connectionService),
                const SizedBox(height: 16),
                
                // Debug Controls
                _buildDebugControls(connectionService),
                const SizedBox(height: 16),
                
                // Debug Log
                Expanded(
                  child: _buildDebugLog(connectionService),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildStatusCard(connection_service.ConnectionService service) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Connection Status',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            _buildStatusRow('State', service.connectionState.toString()),
            _buildStatusRow('PC IP', service.pcIp ?? 'Not connected'),
            _buildStatusRow('Status', service.statusMessage),
            _buildStatusRow('Connected', service.isConnected ? 'Yes' : 'No'),
          ],
        ),
      ),
    );
  }

  Widget _buildFileTransferCard(connection_service.ConnectionService service) {
    final progress = service.fileReceiveProgress;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'File Transfer',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            if (progress > 0) ...[
              Text('Progress: ${(progress * 100).toStringAsFixed(1)}%'),
              const SizedBox(height: 8),
              LinearProgressIndicator(
                value: progress,
                backgroundColor: Colors.grey[300],
                valueColor: const AlwaysStoppedAnimation<Color>(Colors.green),
              ),
            ] else
              const Text('No active transfer'),
          ],
        ),
      ),
    );
  }

  Widget _buildDebugControls(connection_service.ConnectionService service) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Debug Controls',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                ElevatedButton.icon(
                  onPressed: service.forceReconnect,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Force Reconnect'),
                ),
                ElevatedButton.icon(
                  onPressed: service.clearDebugLog,
                  icon: const Icon(Icons.clear_all),
                  label: const Text('Clear Log'),
                ),
                ElevatedButton.icon(
                  onPressed: () => _sendTestMessage(service),
                  icon: const Icon(Icons.send),
                  label: const Text('Test Message'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDebugLog(connection_service.ConnectionService service) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Debug Log',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  '${service.debugLog.split('\n').where((line) => line.isNotEmpty).length} entries',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.black87,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey[600]!),
                ),
                child: SingleChildScrollView(
                  reverse: true, // Start from the bottom
                  child: Text(
                    service.debugLog.isEmpty 
                        ? 'No debug logs yet...' 
                        : service.debugLog,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: Colors.greenAccent,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              '$label:',
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: Colors.grey[700],
                fontFamily: value.contains('.') || value.contains(':') 
                    ? 'monospace' 
                    : null,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _sendTestMessage(connection_service.ConnectionService service) {
    if (service.isConnected) {
      service.sendMessage({
        'type': 'test_message',
        'timestamp': DateTime.now().millisecondsSinceEpoch,
        'content': 'Debug test message from Flutter app',
      });
      
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Test message sent!'),
          backgroundColor: Colors.green,
          duration: Duration(seconds: 2),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cannot send test message - not connected to PC'),
          backgroundColor: Colors.orange,
          duration: Duration(seconds: 2),
        ),
      );
    }
  }
}