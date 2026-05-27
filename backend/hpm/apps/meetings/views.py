import os
import requests
from datetime import datetime
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Meeting, MeetingTask, MeetingUsers, Record
from .serializers import MeetingSerializer

# RunPod이 반환하는 priority 문자열 ->DB 정수 변환
PRIORITY_MAP = {
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Lowest": 4,
}


@api_view(["GET"])
def meeting_list(request):
    meetings = Meeting.objects.all().order_by("-meeting_at")
    serializer = MeetingSerializer(meetings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def meeting_detail(request, meeting_id):
    meeting = Meeting.objects.get(meeting_id=meeting_id)
    serializer = MeetingSerializer(meeting)
    return Response(serializer.data)


# 회의 시작
# POST /api/meetings/<meeting_id>/start/
# 프론트가 이 요청을 받으면 동시에 마이크 녹음을 시작함
@api_view(["POST"])
def start_meeting(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    # 이미 진행 중인 회의라면 중복 시작 방지
    if meeting.is_meeting:
        return Response({"error": "이미 진행 중인 회의입니다."}, status=status.HTTP_400_BAD_REQUEST)

    # 회의 상태를 진행 중으로 변경
    meeting.is_meeting = True
    meeting.save()

    # Record 테이블에 row 생성 (녹음 파일은 아직 없으므로 비워둠)
    record = Record.objects.create(meeting=meeting)

    return Response({
        "message": "회의가 시작되었습니다.",
        "meeting_id": meeting_id,
        "record_id": record.record_id,
    }, status=status.HTTP_200_OK)


# 회의 종료 
# POST /api/meetings/<meeting_id>/end/
# 프론트에서 녹음 파일(audio)을 multipart/form-data로 함께 전송
@api_view(["POST"])
def end_meeting(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    # 회의 상태를 종료로 변경
    meeting.is_meeting = False
    meeting.save()

    # 프론트에서 녹음 파일을 보냈다면 저장
    audio_file = request.FILES.get("audio")
    if audio_file:
        # media/records/ 폴더에 meeting_id로 구분해서 저장
        save_dir = os.path.join(settings.MEDIA_ROOT, "records", str(meeting_id))
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, audio_file.name)

        with open(file_path, "wb+") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # Record 테이블에 파일 경로 저장
        record = Record.objects.filter(meeting=meeting).last()
        if record:
            record.record_path = file_path
            record.save()

    return Response({
        "message": "회의가 종료되었습니다.",
        "meeting_id": meeting_id,
    }, status=status.HTTP_200_OK)


# STT 처리
# POST /api/meetings/<meeting_id>/stt/
# 저장된 녹음 파일을 RunPod WhisperX 서버로 전송 -> 텍스트 변환 → DB 저장
@api_view(["POST"])
def stt_transcribe(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    # 해당 회의의 Record 조회 (end_meeting에서 생성된 것)
    record = Record.objects.filter(meeting=meeting).last()
    if not record or not record.record_path:
        return Response(
            {"error": "녹음 파일이 없습니다. 먼저 회의를 종료해주세요."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # RunPod WhisperX 서버에 오디오 파일 전송
    stt_url = settings.RUNPOD_STT_URL
    try:
        with open(record.record_path, "rb") as audio_file:
            filename = os.path.basename(record.record_path)
            response = requests.post(
                stt_url,
                files={"audio": (filename, audio_file, "audio/mp4")},
                timeout=600,  # STT 처리 시간(긴 회의 파일 고려)
            )
        response.raise_for_status()
        data = response.json()
    except FileNotFoundError:
        return Response({"error": "녹음 파일을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    except requests.RequestException as e:
        return Response({"error": f"STT 서버 연결 실패: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

    # WhisperX 응답에서 full_text 추출 ->  record_row_text에 저장
    full_text = data.get("full_text", "")
    record.record_row_text = full_text
    record.save()

    return Response({
        "message": "STT 처리가 완료되었습니다.",
        "meeting_id": meeting_id,
        "record_id": record.record_id,
        "full_text": full_text,
        "segments": data.get("segments", []),  # 화자별 세그먼트
    }, status=status.HTTP_200_OK)


# 회의록 생성
# POST /api/meetings/<meeting_id>/minutes/
# Django가 RunPod에 녹음 파일을 보내고, 받은 회의록 + 태스크를 DB에 저장
@api_view(["POST"])
def generate_minutes(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    # 해당 회의의 STT 텍스트 조회 (다른 팀원이 STT 변환 후 record_row_text에 저장)
    record = Record.objects.filter(meeting=meeting).last()
    if not record or not record.record_row_text:
        return Response({"error": "변환된 텍스트가 없습니다. STT 처리가 완료됐는지 확인해주세요."}, status=status.HTTP_400_BAD_REQUEST)

    # RunPod에 텍스트 전송 -> 회의록 + 태스크 생성 요청
    runpod_url = settings.RUNPOD_MINUTES_URL
    try:
        response = requests.post(
            runpod_url,
            json={"text": record.record_row_text},  # 텍스트를 JSON으로 전송
            timeout=300,  # LLM 처리 시간 고려
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return Response({"error": f"RunPod 연결 실패: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

    # RunPod 응답 파싱
    # 응답 형식: { "cotent": "회의록...", "todo_list": [...] }
    cotent = data.get("cotent", "")
    todo_list = data.get("todo_list", [])

    #회의록 텍스트 저장
    meeting.meeting_document = cotent
    meeting.save()

    #todo_list-> MeetingTask 테이블에 저장
    created_tasks = []
    skipped_tasks = []

    for todo in todo_list:
        owner_name = todo.get("owner", "")
        title = todo.get("title", "")
        content = todo.get("content", "")
        due_date_str = todo.get("due_date", "")
        priority_str = todo.get("priority", "Medium")

        # 담당자 이름으로 MeetingUsers 조회
        meeting_user = MeetingUsers.objects.filter(
            meeting=meeting,
            user__name=owner_name
        ).first()

        if not meeting_user:
            # 담당자를 찾지 못하면 건너뜀
            skipped_tasks.append({"title": title, "reason": f"'{owner_name}' 담당자를 찾을 수 없음"})
            continue

        # due_date 문자열 -> datetime 변환
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            due_date = datetime.now()

        # priority 문자열 -> 정수 변환
        priority_int = PRIORITY_MAP.get(priority_str, 2)  # 기본값 Medium(2)

        MeetingTask.objects.create(
            meeting=meeting,
            meeting_users=meeting_user,
            title=title,
            content=content,
            due_date=due_date,
            priority=priority_int,
            status=0,  # 기본 상태: 미완료
        )
        created_tasks.append({
            "title": title,
            "content": content,
            "owner": owner_name,
            "due_date": due_date_str,
            "priority": priority_str,
        })

    return Response({
        "message": "회의록이 생성되었습니다.",
        "meeting_id": meeting_id,
        "cotent": cotent,
        "created_tasks": created_tasks,
        "skipped_tasks": skipped_tasks,
    }, status=status.HTTP_200_OK)