import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";

type Todo = {
  title: string;
  content: string;
  owner: string;
  due_date: string;
  priority: string;
};

type ResultState = {
  meeting_id: number;
  message: string;
  minutes_data: {
    content: string;
    todo_list: Todo[];
  };
};

export default function MeetingRecordResultPage() {
  const location = useLocation();
  const result = location.state as ResultState | null;

  // 1. 수정 가능한 통합 데이터 상태 정의
  const [meetingMeta, setMeetingMeta] = useState({
    title: "AI 매칭 엔진 고도화 및 프로젝트 진행 상황 점검 회의",
    date: "2025년 5월 29일",
    author: "박수영",
    location: "대륭 17차 18층",
    attendees: "김규호, 김지원, 류지우, 박수영, 황인규",
  });
  const [minutesContent, setMinutesContent] = useState("");
  const [todoList, setTodoList] = useState<Todo[]>([]);
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});

  // 2. 넘어온 초기 데이터 세팅
  useEffect(() => {
    if (result?.minutes_data) {
      setMinutesContent(result.minutes_data.content ?? "");
      setTodoList(result.minutes_data.todo_list ?? []);
    }
  }, [result]);

  const toggleTaskExpand = (meetingId: number, taskIndex: number) => {
    const key = `${meetingId}-${taskIndex}`;
    setExpandedTasks((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleDownloadPDF = () => {
    window.print();
  };

  // 3. 메타 데이터 상단 영역 핸들러
  const handleMetaChange = (field: keyof typeof meetingMeta, value: string) => {
    setMeetingMeta((prev) => ({ ...prev, [field]: value }));
  };

  // 4. 업무(Todo) 리스트 내부 개별 필드 핸들러
  const handleTodoFieldChange = (index: number, field: keyof Todo, value: string) => {
    setTodoList((prev) =>
      prev.map((todo, idx) => (idx === index ? { ...prev[idx], [field]: value } : todo))
    );
  };

  if (!result) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        결과 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="flex min-h-[100vh] w-full justify-center bg-gray-100 p-10 print:bg-white print:p-0">
      <div
        id="pdf-content"
        className="mt-16 w-[900px] rounded-2xl bg-white p-10 shadow print:mt-0 print:w-full print:p-0 print:shadow-none [print-color-adjust:exact]"
      >
        <div className="mb-8 flex w-full items-center justify-between print:mb-6">
          <h1 className="cafe24-font text-4xl font-bold">회의록</h1>

          <button
            onClick={handleDownloadPDF}
            className="cafe24-font flex items-center gap-2 rounded-lg bg-[#EE9F28] px-4 py-2 text-lg font-semibold text-white shadow-sm transition-colors hover:bg-[#d68f24] print:hidden"
          >
            PDF 다운로드
          </button>
        </div>

        <div className="mb-10 overflow-hidden rounded-xl border-2 border-gray-300 bg-white print:mb-0 print:overflow-visible print:rounded-none print:border-none">
          {/* 회의 주제 */}
          <div className="flex min-h-[56px] items-stretch border-b-2 border-gray-300">
            <div className="flex w-[150px] shrink-0 items-center border-r-2 border-gray-300 bg-gray-50 p-4 font-bold">
              회의 주제
            </div>
            <div className="flex flex-1 items-center px-4 py-2">
              <input
                type="text"
                value={meetingMeta.title}
                onChange={(e) => handleMetaChange("title", e.target.value)}
                className="w-full bg-transparent outline-none border-b border-transparent"
              />
            </div>
          </div>

          {/* 회의 일시 / 작성자 */}
          <div className="flex min-h-[56px] items-stretch border-b-2 border-gray-300">
            <div className="flex w-[150px] shrink-0 items-center border-r-2 border-gray-300 bg-gray-50 p-4 font-bold">
              회의 일시
            </div>
            <div className="flex flex-1 items-center border-r-2 border-gray-300 px-4 py-2">
              <input
                type="text"
                value={meetingMeta.date}
                onChange={(e) => handleMetaChange("date", e.target.value)}
                className="w-full bg-transparent outline-none border-b border-transparent"
              />
            </div>

            <div className="flex w-[120px] shrink-0 items-center border-r-2 border-gray-300 bg-gray-50 p-4 font-bold">
              작성자
            </div>
            <div className="flex w-[200px] items-center px-4 py-2">
              <input
                type="text"
                value={meetingMeta.author}
                onChange={(e) => handleMetaChange("author", e.target.value)}
                className="w-full bg-transparent outline-none border-b border-transparent"
              />
            </div>
          </div>

          {/* 회의 장소 */}
          <div className="flex min-h-[56px] items-stretch border-b-2 border-gray-300">
            <div className="flex w-[150px] shrink-0 items-center border-r-2 border-gray-300 bg-gray-50 p-4 font-bold">
              회의 장소
            </div>
            <div className="flex flex-1 items-center px-4 py-2">
              <input
                type="text"
                value={meetingMeta.location}
                onChange={(e) => handleMetaChange("location", e.target.value)}
                className="w-full bg-transparent outline-none border-b border-transparent"
              />
            </div>
          </div>

          {/* 참석자 */}
          <div className="flex min-h-[56px] items-stretch border-b-2 border-gray-300">
            <div className="flex w-[150px] shrink-0 items-center border-r-2 border-gray-300 bg-gray-50 p-4 font-bold">
              참석자
            </div>
            <div className="flex flex-1 items-center px-4 py-2">
              <input
                type="text"
                value={meetingMeta.attendees}
                onChange={(e) => handleMetaChange("attendees", e.target.value)}
                className="w-full bg-transparent outline-none border-b border-transparent"
              />
            </div>
          </div>

          {/* 회의 내용 헤더 */}
          <div className="border-b-2 border-gray-300 bg-gray-50 p-4 text-center text-xl font-bold">
            회의 내용
          </div>

          {/* [변경점 1] 화면 편집용 테스트 영역 (인쇄 시 숨김처리) */}
          <textarea
            value={minutesContent}
            onChange={(e) => setMinutesContent(e.target.value)}
            className="block h-[400px] w-full resize-none border-b-2 border-gray-300 bg-transparent p-4 outline-none transition-colors print:hidden"
          />

          {/* [변경점 2] PDF/인쇄 전용 출력 영역 (화면엔 숨겨져 있다가 인쇄할 때만 나타나며 자동 늘어남) */}
          <div className="hidden min-h-[100px] w-full whitespace-pre-wrap border-b-2 border-gray-300 p-4 text-base leading-relaxed print:block">
            {minutesContent || "등록된 내용이 없습니다."}
          </div>

          {/* 업무 헤더 */}
          <div className="bg-gray-50 p-4 text-center text-xl font-bold">
            업무
          </div>

          <div className="grid grid-cols-13 border-y-2 border-gray-300 bg-gray-50 font-bold">
            <div className="col-span-6 border-r-2 border-gray-300 p-4 text-center">업무 명</div>
            <div className="col-span-2 border-r-2 border-gray-300 p-4 text-center">담당자</div>
            <div className="col-span-3 border-r-2 border-gray-300 p-4 text-center">기한</div>
            <div className="col-span-2 p-4 text-center">우선순위</div>
          </div>

          {/* 업무 리스트 루프 */}
          {todoList.map((todo, index) => {
            const taskKey = `${result.meeting_id}-${index}`;
            const isTaskExpanded = !!expandedTasks[taskKey];

            return (
              <div
                key={index}
                className="border-b-2 border-gray-300 last:border-b-0 print:break-inside-avoid"
              >
                <div className="grid grid-cols-13 items-center">
                  {/* 업무명 편집 */}
                  <div className="col-span-6 flex items-start border-r-2 border-gray-300 p-4">
                    <div
                      contentEditable
                      suppressContentEditableWarning
                      onBlur={(e) => handleTodoFieldChange(index, "title", e.currentTarget.innerText)}
                      className="flex-1 bg-transparent outline-none border-none p-0 text-sm leading-4 min-h-[16px] break-words"
                    >
                      {todo.title}
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleTaskExpand(result.meeting_id, index)}
                      className="ml-2 shrink-0 whitespace-nowrap text-xs font-semibold text-blue-500 hover:underline print:hidden"
                    >
                      {isTaskExpanded ? "접기 ▲" : "더보기 ▼"}
                    </button>
                  </div>

                  {/* 담당자 편집 */}
                  <div className="col-span-2 border-r-2 border-gray-300 p-4">
                    <input
                      type="text"
                      value={todo.owner}
                      onChange={(e) => handleTodoFieldChange(index, "owner", e.target.value)}
                      className="w-full bg-transparent text-center outline-none border-b border-transparent"
                    />
                  </div>

                  {/* 기한 편집 */}
                  <div className="col-span-3 border-r-2 border-gray-300 p-4">
                    <input
                      type="text"
                      value={todo.due_date}
                      onChange={(e) => handleTodoFieldChange(index, "due_date", e.target.value)}
                      className="w-full bg-transparent text-center outline-none border-b border-transparent"
                    />
                  </div>

                  {/* 우선순위 편집 */}
                  <div className="col-span-2 p-4">
                    <input
                      type="text"
                      value={todo.priority}
                      onChange={(e) => handleTodoFieldChange(index, "priority", e.target.value)}
                      className="w-full bg-transparent text-center outline-none border-b border-transparent"
                    />
                  </div>
                </div>

                {/* 더보기 상세 내용 편집 */}
                {isTaskExpanded && (
                  <div className="border-t-2 border-gray-300 bg-gray-50 p-4 print:hidden">
                    <textarea
                      value={todo.content}
                      onChange={(e) => handleTodoFieldChange(index, "content", e.target.value)}
                      className="h-24 w-full resize-none rounded-lg border-2 border-gray-300 bg-white p-3 text-sm outline-none"
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}