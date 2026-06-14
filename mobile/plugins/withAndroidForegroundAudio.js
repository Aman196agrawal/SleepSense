/**
 * Expo config plugin — declares the foreground audio service in AndroidManifest.xml.
 *
 * Android 14+ enforces that any foreground service using the microphone must be
 * declared with android:foregroundServiceType="microphone". Without this declaration
 * the OS will reject startForeground() at runtime and kill the recording.
 *
 * expo-audio's AudioRecorder checks `useForegroundService` (set when `allowsBackgroundRecording`
 * is passed to `setAudioModeAsync`) and calls AudioRecordingService.startService(), which calls
 * startForeground(), protecting the entire app process (including the JS thread) from Doze.
 * This plugin runs at EAS Build / expo prebuild time — it does NOT affect Expo Go.
 */
const { withAndroidManifest } = require('@expo/config-plugins');

// Real class name in expo-audio v1.x (expo.modules.audio.service.AudioRecordingService).
// expo-audio's library manifest already declares this, but we add it at app level too
// to ensure stopWithTask="false" is applied (keeps recording alive if user swipes away).
const FOREGROUND_SERVICE_NAME = 'expo.modules.audio.service.AudioRecordingService';

/**
 * @param {import('@expo/config-plugins').ExpoConfig} config
 * @returns {import('@expo/config-plugins').ExpoConfig}
 */
module.exports = function withAndroidForegroundAudio(config) {
  return withAndroidManifest(config, (cfg) => {
    const manifest = cfg.modResults;
    const app = manifest.manifest.application[0];

    if (!app.service) {
      app.service = [];
    }

    const alreadyDeclared = app.service.some(
      (s) => s.$?.['android:name'] === FOREGROUND_SERVICE_NAME,
    );

    if (!alreadyDeclared) {
      app.service.push({
        $: {
          'android:name':                FOREGROUND_SERVICE_NAME,
          'android:foregroundServiceType': 'microphone',
          'android:exported':            'false',
          'android:stopWithTask':        'false',
        },
      });
    }

    return cfg;
  });
};
