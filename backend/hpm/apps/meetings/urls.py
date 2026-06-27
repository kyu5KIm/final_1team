from django.urls import path
from . import views
from .views import generate_agenda

urlpatterns = [
    # 회의 목록 / 생성
    path("", views.meeting_list),
    # 회의 상세 / 수정
    path("<int:meeting_id>/", views.meeting_detail),
    # 회의 시작
    path("<int:meeting_id>/start/", views.start_meeting),
    # 회의 일시중지 / 재개
    path("<int:meeting_id>/pause/", views.pause_meeting),
    path("<int:meeting_id>/resume/", views.resume_meeting),
    path("<int:meeting_id>/reset-recording/", views.reset_meeting_recording),
    # 회의 종료 (STT + 회의록 생성)
    path("<int:meeting_id>/end/", views.end_meeting),
    # 회의록 생성 (RunPod 별도 호출)
    path("<int:meeting_id>/minutes/", views.generate_minutes),
    # 기초 안건
    path("<int:meeting_id>/agenda/", views.agenda_list),
    path("<int:meeting_id>/agenda/confirm/", views.confirm_agenda),
    path("<int:meeting_id>/ocr-documents/", views.meeting_ocr_documents),
    # 회의록 승인 플로우
    path("<int:meeting_id>/minutes/approve/", views.complete_minutes_review),
    path("<int:meeting_id>/minutes/complete/", views.complete_minutes_review),
    # 태스크
    path("<int:meeting_id>/tasks/", views.task_list),
    path("<int:meeting_id>/tasks/<int:task_id>/", views.task_detail),
    # Jira 등록
    path("<int:meeting_id>/jira/", views.register_jira_tasks),
    # 회의 후 요약 이메일 발송
    path("<int:meeting_id>/email/", views.send_summary_email),
    # 안건생성
    path("<int:meeting_id>/agenda/generate/", views.generate_agenda),
    path("<int:meeting_id>/agenda/status/", views.check_agenda_status),
    # speaker_mapping_list
    path("<int:meeting_id>/speaker-mapping/", views.speaker_mapping_list),
    path("<int:meeting_id>/raw-transcript-only/", views.complete_raw_transcript_only),
    path("<int:meeting_id>/mapped-transcript-only/", views.complete_mapped_transcript_only),
    # 회의 준비 자료
    path("<int:meeting_id>/prep/", views.prep_material_detail),
    path("<int:meeting_id>/prep/generate/", views.generate_prep_material),
    path('<int:meeting_id>/prep/status/', views.check_prep_status),
]
