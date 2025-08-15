// kairos_mobile_app/lib/screens/file_transfer_view.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:kairos_mobile_app/services/api_service.dart';
// --- FIX: Import the ConnectionService ---
import 'package:kairos_mobile_app/services/connection_service.dart';

class FileTransferView extends StatefulWidget {
  const FileTransferView({super.key});

  @override
  State<FileTransferView> createState() => _FileTransferViewState();
}

class _FileTransferViewState extends State<FileTransferView> {
  final TextEditingController _clipboardController = TextEditingController();
  String _pcClipboardContent = 'Press "Get PC Clipboard" to fetch.';
  bool _isLoading = false;
  String _errorMessage = '';

  @override
  void dispose() {
    _clipboardController.dispose();
    super.dispose();
  }

  Future<void> _getPcClipboard() async {
    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });
    try {
      // --- FIX: Get both services ---
      final apiService = Provider.of<ApiService>(context, listen: false);
      final connectionService = Provider.of<ConnectionService>(context, listen: false);
      
      if (connectionService.isConnected && connectionService.pcIp != null) {
        // Pass the IP to the function
        final content = await apiService.getPcClipboard(connectionService.pcIp!);
        setState(() {
          _pcClipboardContent = content;
          _clipboardController.text = content;
        });
      } else {
        throw Exception('Not connected to KAIROS PC.');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: Could not fetch clipboard. ($e)';
        _pcClipboardContent = 'Error fetching clipboard.';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _setPcClipboard() async {
    if (_clipboardController.text.isEmpty) {
      setState(() {
        _errorMessage = 'Please enter text to set to clipboard.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });
    try {
      // --- FIX: Get both services ---
      final apiService = Provider.of<ApiService>(context, listen: false);
      final connectionService = Provider.of<ConnectionService>(context, listen: false);
      
      if (connectionService.isConnected && connectionService.pcIp != null) {
        // Pass the IP to the function
        await apiService.setPcClipboard(_clipboardController.text, connectionService.pcIp!);
        setState(() {
          _errorMessage = 'PC clipboard updated successfully!';
        });
      } else {
        throw Exception('Not connected to KAIROS PC.');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: Could not set clipboard. ($e)';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Shared Clipboard',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.bold,
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: _isLoading ? null : _getPcClipboard,
            icon: _isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.download),
            label: const Text('Get PC Clipboard'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
              backgroundColor: Theme.of(context).colorScheme.secondary,
              foregroundColor: Colors.black,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            _pcClipboardContent,
            style: const TextStyle(fontSize: 16, color: Colors.white70),
            textAlign: TextAlign.center,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _clipboardController,
            decoration: InputDecoration(
              labelText: 'Text to set on PC Clipboard',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
              ),
              filled: true,
              fillColor: Theme.of(context).cardColor,
            ),
            style: const TextStyle(color: Colors.white),
            maxLines: 3,
          ),
          const SizedBox(height: 10),
          ElevatedButton.icon(
            onPressed: _isLoading ? null : _setPcClipboard,
            icon: _isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.upload),
            label: const Text('Set PC Clipboard'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
              backgroundColor: Theme.of(context).colorScheme.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
          if (_errorMessage.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              _errorMessage,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
              textAlign: TextAlign.center,
            ),
          ],
          const Spacer(),
        ],
      ),
    );
  }
}