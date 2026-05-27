import { useRef, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

export default function MeetingRecordResultPage() {
    return (
        <div className="w-full h-[calc(100vh-60px)] flex items-center justify-center">
        <div className="flex flex-col items-start text-left gap-4">
            <h1 className="text-3xl font-bold cafe24-font">회의록</h1>
            <p className="text-3xl font-bold cafe24-font">
            회의 주제
            </p>
            <input
            type="text"
            placeholder="입력하세요"
            className="w-[400px] rounded-xl bg-white px-4 py-3 outline-none"
            />
            <p className="text-3xl font-bold cafe24-font">
            회의 일시
            </p>
            <input
            type="text"
            placeholder="입력하세요"
            className="w-[400px] rounded-xl bg-white px-4 py-3 outline-none"
            />
        </div>
        </div>
    )
}