export interface Meeting {
  meeting_id: number;
  title: string;
  location: string;
  meeting_at: string;
  meeting_document: string | null;
  is_meeting: boolean;
  project: number;
  meeting_users: number;
}