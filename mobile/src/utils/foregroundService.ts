/**
 * Android foreground service notification manager (FR-REC-003).
 *
 * Android requires every foreground service to post a visible, user-facing
 * notification for as long as the service runs. We use expo-notifications to
 * post an "ongoing" sticky notification when recording starts; the notification
 * is cancelled when recording stops.
 *
 * On iOS, UIBackgroundModes = ["audio"] (declared in app.json) handles background
 * recording at the OS level — no foreground service concept exists.
 */
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

const CHANNEL_ID      = 'sleep-recording';
const NOTIFICATION_ID = 'foreground-recording-active';

async function ensureChannelCreated(): Promise<void> {
  await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
    name:                  'Sleep Recording',
    importance:            Notifications.AndroidImportance.DEFAULT,
    lockscreenVisibility:  Notifications.AndroidNotificationVisibility.PUBLIC,
    sound:                 null,
    enableVibrate:         false,
    showBadge:             false,
    description:           'Shown while SleepSense is recording your sleep audio.',
  });
}

/**
 * Post an ongoing sticky notification that keeps the foreground service visible.
 * Call once immediately after recording starts on Android.
 */
export async function startForegroundAudioNotification(): Promise<void> {
  if (Platform.OS !== 'android') return;

  await ensureChannelCreated();

  await Notifications.scheduleNotificationAsync({
    identifier: NOTIFICATION_ID,
    content: {
      title:       'SleepSense Recording',
      body:        'Recording your sleep… tap to return to the app.',
      data:        {},
      sticky:      true,
      autoDismiss: false,
      color:       '#0A2463',
      priority:    Notifications.AndroidNotificationPriority.DEFAULT,
    } as Notifications.NotificationContentInput,
    trigger: null,
  });
}

/**
 * Cancel the foreground notification.
 * Call once after recording has fully stopped on Android.
 */
export async function stopForegroundAudioNotification(): Promise<void> {
  if (Platform.OS !== 'android') return;

  try {
    await Notifications.dismissNotificationAsync(NOTIFICATION_ID);
  } catch (_) {}
  try {
    await Notifications.cancelScheduledNotificationAsync(NOTIFICATION_ID);
  } catch (_) {}
}
