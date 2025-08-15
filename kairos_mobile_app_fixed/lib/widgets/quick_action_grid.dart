// kairos_mobile_app/lib/widgets/quick_action_grid.dart
import 'package:flutter/material.dart';
import 'package:kairos_mobile_app/services/api_service.dart';
// --- FIX: Import the ConnectionService ---
import 'package:kairos_mobile_app/services/connection_service.dart'; 
import 'package:kairos_mobile_app/services/headset_service.dart';
import 'package:kairos_mobile_app/theme.dart';
import 'package:provider/provider.dart';

class QuickAction {
  final String title;
  final IconData icon;
  final Future<void> Function(BuildContext context) onTap;

  QuickAction({required this.title, required this.icon, required this.onTap});
}

class QuickActionGrid extends StatelessWidget {
  const QuickActionGrid({super.key});

  @override
  Widget build(BuildContext context) {
    final List<QuickAction> actions = [
      QuickAction(
        title: 'Share Clipboard',
        icon: Icons.content_paste_go_rounded,
        onTap: (context) async => debugPrint('Share Clipboard Tapped')
      ),
      QuickAction(
        title: 'Send File',
        icon: Icons.upload_file_rounded,
        onTap: (context) async => debugPrint('Send File Tapped')
      ),
      QuickAction(
        title: 'Handoff Audio to PC',
        icon: Icons.headset_mic_rounded,
        onTap: (context) async {
          debugPrint('Handoff to PC tapped');
          final headsetName = await HeadsetService.findConnectedHeadsetName();
          if (headsetName != null && context.mounted) {
            // --- FIX: Get both services and pass the IP ---
            final apiService = Provider.of<ApiService>(context, listen: false);
            final connectionService = Provider.of<ConnectionService>(context, listen: false);
            if (connectionService.isConnected && connectionService.pcIp != null) {
              await apiService.sendHeadsetHandoffToPc(headsetName, connectionService.pcIp!);
            } else {
              debugPrint("Not connected to PC, cannot send command.");
            }
          } else {
            debugPrint("No headset found or context is not available.");
          }
        },
      ),
      QuickAction(
        title: 'Media Control',
        icon: Icons.play_circle_fill_rounded,
        onTap: (context) async => debugPrint('Media Control Tapped')
      ),
    ];

    return GridView.builder(
      physics: const NeverScrollableScrollPhysics(),
      shrinkWrap: true,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 1.2,
      ),
      itemCount: actions.length,
      itemBuilder: (context, index) {
        final action = actions[index];
        return _buildActionCard(context, action);
      },
    );
  }

  Widget _buildActionCard(BuildContext context, QuickAction action) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => action.onTap(context),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(action.icon, size: 40, color: AppColors.secondaryColor),
            const SizedBox(height: 12),
            Text(
              action.title,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}