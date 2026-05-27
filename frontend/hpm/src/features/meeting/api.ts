import axios from "axios";
import type { Meeting } from "../../types/meeting";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api",
});

export const getMeetings = async (): Promise<Meeting[]> => {
  const response = await api.get<Meeting[]>("/meetings/");
  console.log("결과는",response.data)
  return response.data;
};

export const getMeetingDetail = async (
  meetingId: number
): Promise<Meeting> => {
  const response = await api.get<Meeting>(`/meetings/${meetingId}/`);
  return response.data;
};