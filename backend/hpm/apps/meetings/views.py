import os
import requests
from datetime import datetime
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Meeting, MeetingTask, MeetingUsers, Record
from .serializers import MeetingSerializer

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

@api_view(["POST"])
def start_meeting(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    if meeting.is_meeting:
        return Response({"error": "이미 진행 중인 회의입니다."}, status=status.HTTP_400_BAD_REQUEST)

    meeting.is_meeting = True
    meeting.save()

    Record.objects.create(meeting=meeting)
    return Response({"message": "회의가 시작되었습니다.", "meeting_id": meeting_id}, status=status.HTTP_200_OK)


@api_view(["POST"])
def end_meeting(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    meeting.is_meeting = False
    meeting.save()

    audio_file = request.FILES.get("audio")
    if audio_file:
        save_dir = os.path.join(settings.MEDIA_ROOT, "records", str(meeting_id))
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, audio_file.name)

        with open(file_path, "wb+") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # 💡 런팟 베이스 URL 빌드 자동 보정
        base_runpod_url = "https://grud52cfqhygb3-8000.proxy.runpod.net"
        stt_url = f"{base_runpod_url.rstrip('/')}/transcribe"

        with open(file_path, "rb") as f:
            response = requests.post(stt_url, files={"file": f}, timeout=600) # file 키값 수정

        result = response.json()
        full_text = result.get("full_text", "")

        record = Record.objects.filter(meeting=meeting).last()
        if record:
            record.record_path = file_path
            record.record_row_text = full_text
            record.save()

            txt_dir = os.path.join(settings.MEDIA_ROOT, "texts", str(meeting_id))
            os.makedirs(txt_dir, exist_ok=True)
            with open(os.path.join(txt_dir, f"meeting-{meeting_id}.txt"), "w", encoding="utf-8") as f:
                f.write(full_text)

            # 💡 슬래시 버그 방지용 주소 조합 고도화
            minutes_base = getattr(settings, "RUNPOD_MINUTES_URL", base_runpod_url)
            minutes_url = f"{minutes_base.rstrip('/')}"

            minutes_response = requests.post(minutes_url, json={"text": full_text}, timeout=300)
            minutes_response.raise_for_status()
            
            minutes_data = minutes_response.json()

            meeting.meeting_document = minutes_data.get("content", "")
            meeting.save()

    return Response(
    {
        "message": "회의가 종료되고 기록이 정상 반영되었습니다.",
        "meeting_id": meeting_id,
        "minutes_data": minutes_data,
    },
    status=status.HTTP_200_OK,
)


@api_view(["POST"])
def generate_minutes(request, meeting_id):
    try:
        meeting = Meeting.objects.get(meeting_id=meeting_id)
    except Meeting.DoesNotExist:
        return Response({"error": "회의를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    record = Record.objects.filter(meeting=meeting).last()
    if not record or not record.record_row_text:
        return Response({"error": "변환된 텍스트가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

    # 💡 여기서도 엔드포인트 누락 버그 해결
    minutes_base = getattr(settings, "RUNPOD_MINUTES_URL", "https://grud52cfqhygb3-8000.proxy.runpod.net/")
    minutes_url = f"{minutes_base.rstrip('/')}/generate"

    try:
        response = requests.post(minutes_url, json={"text": record.record_row_text}, timeout=300)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return Response({"error": f"RunPod 연결 실패: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

    content = data.get("content", "")
    todo_list = data.get("todo_list", [])

    meeting.meeting_document = content
    meeting.save()

    created_tasks = []
    skipped_tasks = []

    for todo in todo_list:
        owner_name = todo.get("owner", "")
        title = todo.get("title", "")
        task_content = todo.get("content", "")
        due_date_str = todo.get("due_date", "")
        priority_str = todo.get("priority", "Medium")

        meeting_user = MeetingUsers.objects.filter(meeting=meeting, user__name=owner_name).first()

        if not meeting_user:
            skipped_tasks.append({"title": title, "reason": f"'{owner_name}' 담당자를 찾을 수 없음"})
            continue

        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            due_date = datetime.now()

        MeetingTask.objects.create(
            meeting=meeting,
            meeting_users=meeting_user,
            title=title,
            content=task_content,
            due_date=due_date,
            priority=PRIORITY_MAP.get(priority_str, 2),
            status=0,
        )
        created_tasks.append({"title": title, "owner": owner_name, "priority": priority_str})

    return Response({
        "message": "회의록 및 태스크 생성이 완료되었습니다.",
        "meeting_id": meeting_id,
        "content": content,
        "created_tasks": created_tasks,
        "skipped_tasks": skipped_tasks,
    }, status=status.HTTP_200_OK)