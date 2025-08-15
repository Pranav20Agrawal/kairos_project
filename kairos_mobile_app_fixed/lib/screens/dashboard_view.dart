// kairos_mobile_app/lib/screens/dashboard_view.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
// --- FIX: Import the new service ---
import 'package:kairos_mobile_app/services/connection_service.dart'; 
import 'package:kairos_mobile_app/theme.dart';
import 'package:kairos_mobile_app/widgets/device_status_widget.dart';
import 'package:kairos_mobile_app/widgets/quick_action_grid.dart';
import 'package:provider/provider.dart';

class DashboardView extends StatelessWidget {
  const DashboardView({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const DeviceStatusWidget(),
            const SizedBox(height: 16),
            
            // This now correctly listens to ConnectionService
            Consumer<ConnectionService>(
              builder: (context, connectionService, child) {
                final bool isTransferring = connectionService.fileReceiveProgress > 0 &&
                    connectionService.fileReceiveProgress < 1;
                
                return AnimatedOpacity(
                  opacity: isTransferring ? 1.0 : 0.0,
                  duration: const Duration(milliseconds: 300),
                  child: isTransferring 
                      ? _buildFileTransferProgress(context, connectionService) 
                      : const SizedBox.shrink(),
                );
              },
            ),
            const SizedBox(height: 24),
            Text(
              'Quick Actions',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            const QuickActionGrid(),
            const SizedBox(height: 24),
            Text(
              'Recent Activity',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 40.0),
                child: Text(
                  'No recent activity yet.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
                ),
              ),
            ),
          ],
        ),
      ),
    )
    .animate()
    .fadeIn(duration: 500.ms)
    .slideY(begin: 0.1, end: 0, duration: 500.ms, curve: Curves.easeOut);
  }

  // --- FIX: Changed the parameter type from BleService to ConnectionService ---
  Widget _buildFileTransferProgress(BuildContext context, ConnectionService connectionService) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Receiving File...',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: LinearProgressIndicator(
                    value: connectionService.fileReceiveProgress,
                    backgroundColor: AppColors.card,
                    color: AppColors.secondaryColor,
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  '${(connectionService.fileReceiveProgress * 100).toStringAsFixed(0)}%',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}