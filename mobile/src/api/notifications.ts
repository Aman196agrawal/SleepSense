import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function requestNotificationPermissions(): Promise<boolean> {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('bedtime', {
      name: 'Bedtime Reminder',
      importance: Notifications.AndroidImportance.HIGH,
      sound: 'default',
    });
    return true;
  }
  const { status } = await Notifications.requestPermissionsAsync();
  return status === 'granted';
}

export async function scheduleBedtimeReminder(hhmm: string): Promise<void> {
  const granted = await requestNotificationPermissions();
  if (!granted) return;

  await Notifications.cancelAllScheduledNotificationsAsync();

  const [h, m] = hhmm.split(':').map(Number);
  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'Time for bed 🌙',
      body: 'Your SleepSense session is waiting. Start recording to track your sleep tonight.',
      sound: 'default',
    },
    trigger: {
      hour: h,
      minute: m,
      repeats: true,
    } as any,
  });
}

export async function cancelBedtimeReminder(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
}
