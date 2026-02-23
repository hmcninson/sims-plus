/**
 * SIMS Plus - Communication Settings Type Definitions
 */

export interface SMSSettings {
  sender_id: string;
  attendance_alerts_enabled: boolean;
  fee_reminders_enabled: boolean;
}

export interface EmailSettings {
  from_email: string | null;
  from_name: string | null;
  reply_to: string | null;
  signature: string | null;
}

export interface NotificationDefaults {
  report_card_notifications: boolean;
  event_announcements: boolean;
  weekly_digest: boolean;
}

export interface CommunicationSettings {
  sms: SMSSettings;
  email: EmailSettings;
  notifications: NotificationDefaults;
}
