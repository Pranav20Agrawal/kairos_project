// kairos_mobile_app/lib/widgets/device_status_widget.dart
import 'package:flutter/material.dart';
// --- FIX: Import the new service ---
import 'package:kairos_mobile_app/services/connection_service.dart';
import 'package:kairos_mobile_app/theme.dart';
import 'package:provider/provider.dart';

class DeviceStatusWidget extends StatelessWidget {
  const DeviceStatusWidget({super.key});

  @override
  Widget build(BuildContext context) {
    // --- FIX: Listen to ConnectionService instead of BleService ---
    return Consumer<ConnectionService>(
      builder: (context, connectionService, child) {
        return Card(
          elevation: 4,
          shadowColor: Colors.black.withOpacity(0.5),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Row(
              children: [
                Icon(
                  connectionService.isConnected ? Icons.check_circle_rounded : Icons.cancel_rounded,
                  color: connectionService.isConnected ? AppColors.secondaryColor : AppColors.error,
                  size: 32,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        connectionService.isConnected ? 'KAIROS PC Connected' : 'Disconnected',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                      ),
                      Text(
                        connectionService.statusMessage,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: AppColors.textSecondary,
                            ),
                      ),
                    ],
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