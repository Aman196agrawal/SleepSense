/**
 * Android foreground service — delegated to expo-audio (v1.x).
 *
 * When `setAudioModeAsync({ allowsBackgroundRecording: true })` is called before
 * recording starts, expo-audio sets `recorder.useForegroundService = true`. On the
 * first `recorder.record()` call, expo-audio's native layer calls
 * `AudioRecordingService.startService()` which posts a persistent notification and
 * calls `startForeground(FOREGROUND_SERVICE_TYPE_MICROPHONE)`. This protects the
 * entire app process — including the JS thread and its setInterval timers — from
 * being killed by Android's Doze mode during an all-night recording session.
 *
 * The service is declared in AndroidManifest.xml as:
 *   expo.modules.audio.service.AudioRecordingService
 *   foregroundServiceType="microphone"  stopWithTask="false"
 *
 * These functions are kept as stubs so RecordScreen.tsx call sites compile without
 * change. They are intentionally no-ops.
 */

export async function startForegroundAudioNotification(): Promise<void> {
  // no-op: expo-audio starts the real Android foreground service via
  // allowsBackgroundRecording: true in setAudioModeAsync.
}

export async function stopForegroundAudioNotification(): Promise<void> {
  // no-op: expo-audio stops the service automatically when the recorder is released.
}
