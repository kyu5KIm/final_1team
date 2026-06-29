from django.db import models
from apps.users.models import Users


class Meeting(models.Model):
    class MeetingStatus(models.IntegerChoices):
        SCHEDULED   = 0, "회의 전"
        IN_PROGRESS = 1, "회의 진행 중"
        FINISHED    = 2, "회의 후"

    meeting_id = models.AutoField(primary_key=True, verbose_name="회의 식별 번호")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, db_column="project_id", verbose_name="프로젝트"
    )
    creator = models.ForeignKey(
        Users, on_delete=models.PROTECT, db_column="creator_id",
        related_name="created_meetings", null=True, verbose_name="회의 생성자"
    )

    title            = models.CharField(max_length=90, verbose_name="회의 주제")
    location         = models.CharField(max_length=150, blank=True, verbose_name="회의 장소")
    meeting_at       = models.DateTimeField(verbose_name="회의 일시")
    meeting_document = models.TextField(null=True, blank=True, verbose_name="회의록")
    during_time      = models.CharField(max_length=20, null=True, blank=True, verbose_name="회의 진행 시간")
    meeting_status   = models.IntegerField(
        choices=MeetingStatus.choices, default=MeetingStatus.SCHEDULED, verbose_name="회의 상태"
    )
    is_meeting_approve = models.BooleanField(default=False, verbose_name="회의록 승인 여부")
    is_paused = models.BooleanField(default=False, verbose_name="일시 정지 여부")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성 일시")

    class Meta:
        db_table = "meeting"
        verbose_name = "회의"
        verbose_name_plural = "회의"


class Record(models.Model):
    record_id = models.AutoField(primary_key=True, verbose_name="녹음 원문 식별 번호")
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, db_column="meeting_id", verbose_name="회의")

    class Meta:
        db_table = "record"


class MeetingUsers(models.Model):
    meeting_users_id = models.AutoField(primary_key=True, verbose_name="회의 참여자 식별 번호")
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, db_column="meeting_id", verbose_name="회의")
    user    = models.ForeignKey(Users,   on_delete=models.CASCADE, db_column="user_id", verbose_name="참여자")

    class Meta:
        db_table = "meeting_users"


class MeetingAgendas(models.Model):
    agenda_id = models.AutoField(primary_key=True, verbose_name="안건 식별 번호")
    meeting   = models.ForeignKey(Meeting, on_delete=models.CASCADE, db_column="meeting_id", verbose_name="회의 식별 번호")
    content   = models.TextField(verbose_name="안건 내용")

    class Meta:
        db_table = "meeting_agendas"


class MeetingPreparation(models.Model):
    preration_id = models.AutoField(primary_key=True, verbose_name="회의 준비 자료 식별 번호")
    meeting  = models.ForeignKey(Meeting, on_delete=models.CASCADE, db_column="meeting_id", verbose_name="회의")
    purpose = models.TextField(null=True, verbose_name="회의 목적")
    project_status = models.TextField(null=True, verbose_name="프로젝트 현재 상태")
    rule = models.TextField(null=True, verbose_name="규정")
    effect = models.TextField(null=True, verbose_name="회의 종료 후 기대효과")

    class Meta:
        db_table = "meeting_preparation"

class PreparationDocument(models.Model):
    prepartion_document_id = models.AutoField(primary_key=True, verbose_name="참고 자료 식별번호")
    preparation = models.ForeignKey(
        MeetingPreparation, 
        on_delete=models.CASCADE,
        db_column="preration_id", 
        verbose_name="회의 준비 자료 식별 번호"
    )
    document_id = models.IntegerField(
        verbose_name="내부문서 식별번호"
    )
    class Meta:
        db_table = "prepartion_document"


class MeetingTask(models.Model):
    class TaskStatus(models.IntegerChoices):
        TODO = 0, "미완료"
        IN_PROGRESS = 1, "진행중"
        DONE = 2, "완료"
    class PriorityChoices(models.TextChoices):
        HIGHEST = "Highest", "Highest"
        HIGH = "High", "High"
        MEDIUM = "Medium", "Medium"
        LOW = "Low", "Low"
        LOWEST = "Lowest", "Lowest"
    meeting_task_id = models.AutoField(primary_key=True, verbose_name="태스크 식별 번호")
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, db_column="meeting_id", verbose_name="회의"
    )
    title = models.CharField(max_length=255, verbose_name="업무 제목")
    content = models.TextField(null=True, blank=True, verbose_name="업무 내용")
    meeting_users   = models.ForeignKey(
        MeetingUsers,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column="meeting_users_id",
        verbose_name="담당자"
    )
    due_date = models.DateField(null=True, blank=True, verbose_name="업무 마감 기한")
    priority = models.CharField(
        max_length=20, 
        choices=PriorityChoices.choices, 
        null=True, 
        blank=True, 
        verbose_name="업무 우선순위"
    )
    status = models.IntegerField(
        choices=TaskStatus.choices, default=TaskStatus.TODO, verbose_name="업무 상태"
    )
    class Meta:
        db_table = "meeting_task"

class RecordUtterance(models.Model):
    utterance_id = models.AutoField(primary_key=True, verbose_name="발화 내역 식별 번호")
    record = models.ForeignKey(
        Record, 
        on_delete=models.CASCADE, 
        db_column="record_id", 
        verbose_name="녹음 원문"
    )
    
    meeting_users = models.ForeignKey(
        MeetingUsers, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        db_column="meeting_users_id", 
        verbose_name="실제 참여자"
    )
    
    speaker = models.CharField(max_length=20, verbose_name="매핑전 발화자")
    time = models.CharField(max_length=30, verbose_name="발화 시각")
    content = models.TextField(verbose_name="발화 내용")

    class Meta:
        db_table = "record_utterance"
        verbose_name = "발화 내역"
        verbose_name_plural = "발화 내역"


class MeetingOcrDocument(models.Model):
    class Kind(models.TextChoices):
        AGENDA = "agenda", "기초 안건"
        PREP = "prep", "회의 준비 자료"

    meeting_ocr_document_id = models.AutoField(primary_key=True, verbose_name="OCR 문서 식별번호")
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, db_column="meeting_id", verbose_name="회의"
    )
    document_id = models.IntegerField(verbose_name="내부문서 식별번호")
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="용도")

    class Meta:
        db_table = "meeting_ocr_document"