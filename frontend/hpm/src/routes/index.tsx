import { createBrowserRouter } from "react-router-dom";

import Layout from "../components/layout/Layout";
import MeetingListPage from "../pages/meeting/MeetingListPage";
import MeetingRecordStart from "../pages/meeting/MeetingRecordStart";
import MeetingRecord from "../pages/meeting/MeetingRecord"
import MeetingRecordResult from "../pages/meeting/MeetingRecordResult";
const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      {
        path: "/meeting",
        element: <MeetingListPage />,
      },
      {
        path: "/meeting/record/start",
        element: <MeetingRecordStart />,
      },
      {
        path: "/meeting/recording",
        element: <MeetingRecord />,
      },
      {
        path: "/meeting/record/result",
        element: <MeetingRecordResult />,
      },
    ],
  },
]);

export default router;