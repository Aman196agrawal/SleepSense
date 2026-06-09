/**
 * Expo config plugin — declares the foreground audio service in AndroidManifest.xml.
 *
 * Android 14+ enforces that any foreground service using the microphone must be
 * declared with android:foregroundServiceType="microphone". Without this declaration
 * the OS will reject startForeground() at runtime and kill the recording.
 *
 * expo-audio's Android AudioRecorder binds to this service class when the manifest
 * entry is present, which keeps the recording alive while the app is in the background.
 * This plugin runs at EAS Build / expo prebuild time — it does NOT affect Expo Go.
 */
const { withAndroidManifest } = require('@expo/config-plugins');

const FOREGROUND_SERVICE_NAME = 'expo.modules.audio.AudioRecordingForegroundService';

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
