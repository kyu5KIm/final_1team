import { useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import logo from "../../assets/start.png";
import stop from "../../assets/stop.png";

type ChatMessage = {
  role: "user" | "bot";
  content: string;
};

export default function MeetingRecordStartPage() {
  const navigate = useNavigate();

  const [recording, setRecording] = useState(false);
  const [loading, setLoading] = useState(false);

  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // 챗봇 state
  const [chatInput, setChatInput] = useState("");

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "bot",
      content: "안녕하세요. 회의 관련해서 궁금한 걸 물어보세요.",
    },
  ]);

  const [chatLoading, setChatLoading] = useState(false);

  // 스크롤 조작을 위한 Ref 추가
  const chatWindowRef = useRef<HTMLDivElement | null>(null);

  // 메시지 목록이나 로딩 상태가 바뀔 때마다 스크롤을 맨 아래로 이동
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTo({
        top: chatWindowRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [chatMessages, chatLoading]);

  // 녹음 시작
  const startRecording = async () => {
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });

        const url = URL.createObjectURL(audioBlob);

        setAudioUrl(url);

        await uploadAudio(audioBlob);

        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();

      setRecording(true);
    } catch (err) { 
      console.error("마이크 접근 실패:", err);
      alert("마이크 권한을 허용해주세요.");
    }
  };

  // 녹음 종료
  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  // 회의록 업로드
  const uploadAudio = async (blob: Blob) => {
    const ok = window.confirm("회의록을 생성하시겠습니까?");

    if (!ok) return;

    setLoading(true);

    try {
      const formData = new FormData();

      formData.append("audio", blob, "meeting-1.webm");

      const res = await fetch(
        "http://localhost:8000/api/meetings/1/end/",
        {
          method: "POST",
          body: formData,
        },
      );

      const data = await res.json();

      console.log(data);

      navigate("/meeting/record/result", {
        state: data,
      });
    } catch (error) {
      console.error(error);

      alert("회의록 생성 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  // 챗봇 전송
  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const question = chatInput.trim();

    // 사용자 메시지 추가
    setChatMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: question,
      },
    ]);

    setChatInput("");

    setChatLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8088/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
        }),
      });

      const data = await res.json();

      console.log(data);

      // 챗봇 응답 추가
      setChatMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: data.answer ?? "답변을 불러오지 못했습니다.",
        },
      ]);
    } catch (err) {
      console.error(err);

      setChatMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: "챗봇 요청 중 오류가 발생했습니다.",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)] flex-col px-6">
      <section className="flex h-full gap-6"> {/* 좌우 여백을 위해 gap 추가 */}

        {/* 로딩 */}
        {loading && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="rounded-2xl bg-white px-10 py-8 text-center shadow-xl">
              <p className="cafe24-font text-2xl">
                회의록 생성 중입니다...
              </p>
            </div>
          </div>
        )}

        {/* 왼쪽 */}
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center text-center">

            <p className="cafe24-font mb-10 text-3xl text-gray-500">
              {recording
                ? "회의가 녹음 중 입니다."
                : "버튼을 눌러 회의 녹음을 시작하세요"}
            </p>

            <button onClick={recording ? stopRecording : startRecording}>
              <img
                src={recording ? stop : logo}
                alt="record-button"
                className="h-40 w-40"
              />
            </button>
          </div>
        </div>

        {/* 오른쪽 챗봇 (너비를 w-[400px]에서 w-[500px]로 확장) */}
        {recording && (
          <div className="mt-23 flex h-[calc(100vh-120px)] w-[500px] flex-col rounded-2xl border border-gray-200 bg-gray-100 p-5 shadow-sm">

            <h2 className="cafe24-font mb-4 text-2xl">
              회의 도우미 챗봇
            </h2>

            {/* 채팅 영역 (ref={chatWindowRef} 추가, 말풍선 최대 너비 설정을 위해 max-w-[85%] 지정 가능) */}
            <div 
              ref={chatWindowRef}
              className="flex h-[80%] flex-col gap-3 overflow-y-auto rounded-xl bg-gray-100 p-4"
            >

              {chatMessages.map((msg, index) => (
                <div
                  key={index}
                  className={
                    msg.role === "user"
                      ? "self-end rounded-2xl bg-blue-500 px-4 py-2 text-white max-w-[85%] break-words"
                      : "self-start rounded-2xl bg-white px-4 py-2 shadow max-w-[85%] break-words"
                  }
                >
                  {msg.content}
                </div>
              ))}

              {chatLoading && (
                <div className="self-start rounded-2xl bg-white px-4 py-2 shadow">
                  답변 생성 중...
                </div>
              )}
            </div>

            {/* 입력창 */}
            <div className="mt-auto flex gap-2 pt-4">

              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    sendChat();
                  }
                }}
                placeholder="메시지를 입력하세요"
                className="flex-1 rounded-xl border bg-white px-3 py-2 outline-none"
              />

              <button
                onClick={sendChat}
                className="rounded-xl bg-black px-4 py-2 text-white hover:bg-gray-850 transition"
              >
                전송
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}