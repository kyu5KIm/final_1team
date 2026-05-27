import { useEffect, useState } from "react";

import { getMeetings } from "../../features/meeting/api";
import type { Meeting } from "../../types/meeting";

export default function MeetingRecord() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);

  useEffect(() => {
    getMeetings().then(setMeetings);
  }, []);

  return (
    <div>
      <h1>gp</h1>

      {meetings.map((meeting) => (
        <div key={meeting.meeting_id}>
          <h3>{meeting.title}</h3>
          <p>{meeting.location}</p>
        </div>
      ))}
    </div>
  );
}