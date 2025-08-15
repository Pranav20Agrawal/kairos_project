// lib/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class ApiService extends ChangeNotifier {
  // NOTE: This class is now "stateless" regarding the IP address.
  // It does not store or manage the IP. It receives the correct IP
  // for every request, which prevents race conditions on startup.

  /// Sends a command to the PC to take over the headset connection from the phone.
  Future<void> sendHeadsetHandoffToPc(String headsetName, String pcIp) async {
    try {
      final response = await http.post(
        Uri.parse('http://$pcIp:8000/execute_action'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'intent': 'HEADSET_HANDOFF_TO_PC',
          'entity': headsetName,
        }),
      );
      if (response.statusCode != 200) {
        throw Exception('Failed to send handoff command: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error sending headset handoff to PC: $e');
      rethrow;
    }
  }

  /// Sends a raw text command to the PC for processing.
  Future<void> sendTextCommand(String command, String pcIp) async {
    try {
      final response = await http.post(
        Uri.parse('http://$pcIp:8000/process_text_command'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'command': command}),
      );
      if (response.statusCode != 200) {
        throw Exception('Failed to send command: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error sending text command: $e');
      rethrow;
    }
  }

  /// Gets the current clipboard content from the PC.
  Future<String> getPcClipboard(String pcIp) async {
    try {
      final response = await http.get(Uri.parse('http://$pcIp:8000/clipboard'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return data['content'] ?? 'No content found.';
      } else {
        throw Exception('Failed to get clipboard: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error getting clipboard: $e');
      rethrow;
    }
  }

  /// Sets the PC's clipboard to the provided content.
  Future<void> setPcClipboard(String content, String pcIp) async {
    try {
      final response = await http.post(
        Uri.parse('http://$pcIp:8000/clipboard'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'content': content}),
      );
      if (response.statusCode != 200) {
        throw Exception('Failed to set clipboard: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error setting clipboard: $e');
      rethrow;
    }
  }

  /// Uploads a file from the phone to the PC.
  Future<Map<String, dynamic>> uploadFileToPc(String filePath, String fileName, String pcIp) async {
    try {
      final uri = Uri.parse('http://$pcIp:8000/upload_file');
      final request = http.MultipartRequest('POST', uri)
        ..files.add(await http.MultipartFile.fromPath('file', filePath, filename: fileName));

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to upload file: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error uploading file: $e');
      rethrow;
    }
  }

  /// Executes a predefined action or macro on the PC.
  Future<void> executePcAction(String intent, String pcIp, {String? entity}) async {
    try {
      final response = await http.post(
        Uri.parse('http://$pcIp:8000/execute_action'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'intent': intent,
          if (entity != null) 'entity': entity,
        }),
      );
      if (response.statusCode != 200) {
        throw Exception('Failed to execute action: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error executing PC action: $e');
      rethrow;
    }
  }
}