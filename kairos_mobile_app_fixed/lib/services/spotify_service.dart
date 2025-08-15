// // kairos_mobile_app/lib/services/spotify_service.dart
// import 'package:flutter/foundation.dart';
// import 'package:spotify_sdk/spotify_sdk.dart';

// class SpotifyService {
  
//   // These should match what you set up in the Spotify Developer Dashboard
//   static const String _clientId = "YOUR_SPOTIFY_CLIENT_ID"; // <-- PASTE YOUR CLIENT ID HERE
//   static const String _redirectUrl = "kairos-app-login://callback";

//   // This method now serves as our connection check. It returns true on success.
//   static Future<bool> connectToSpotify() async {
//     try {
//       debugPrint("Connecting to Spotify SDK...");
//       var result = await SpotifySdk.connectToSpotifyRemote(
//         clientId: _clientId,
//         redirectUrl: _redirectUrl,
//       );
//       if (result) {
//         debugPrint("Successfully connected to Spotify.");
//       } else {
//         debugPrint("Failed to connect to Spotify. Is the app installed and running?");
//       }
//       return result;
//     } catch (e) {
//       debugPrint("Error connecting to Spotify: $e");
//       return false;
//     }
//   }

//   // Method to handle the handoff with precise playback
//   static Future<void> playTrack(Map<String, dynamic> playbackState) async {
//     try {
//       final trackUri = playbackState['track_uri'] as String?;
//       final progressMs = playbackState['progress_ms'] as int?;

//       if (trackUri == null) {
//         debugPrint("No track URI provided for handoff.");
//         return;
//       }

//       // --- THIS IS THE MODIFIED LOGIC ---
//       // We just try to connect. If it succeeds (or is already connected), we proceed.
//       bool successfulConnection = await connectToSpotify();

//       if (successfulConnection) {
//         debugPrint("Playing URI: $trackUri at ${progressMs ?? 0}ms");
//         await SpotifySdk.play(spotifyUri: trackUri);

//         if (progressMs != null && progressMs > 0) {
//           // Give spotify a moment to start playing before seeking
//           await Future.delayed(const Duration(milliseconds: 500));
//           await SpotifySdk.seekTo(positionedMilliseconds: progressMs);
//           debugPrint("Sought to ${progressMs}ms.");
//         }
//       } else {
//         debugPrint("Could not connect to Spotify to play track.");
//       }
//     } catch (e) {
//       debugPrint("Error playing track on Spotify: $e");
//     }
//   }

//   // --- THIS METHOD IS NO LONGER NEEDED AND HAS BEEN REMOVED ---
//   // static Future<bool> isSpotifyInstalled() async { ... }
// }