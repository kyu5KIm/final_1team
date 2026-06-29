from rest_framework import serializers
from .models import Meeting, MeetingAgendas, MeetingTask, MeetingUsers, Record, RecordUtterance


def build_meeting_participants(meeting):
    participants = []
    seen_user_ids = set()

    if meeting.creator_id and meeting.creator:
        creator_meeting_user = MeetingUsers.objects.filter(
            meeting=meeting,
            user=meeting.creator,
        ).first()
        participants.append({
            "meeting_users_id": creator_meeting_user.meeting_users_id if creator_meeting_user else None,
            "user_id": meeting.creator.users_id,
            "name": meeting.creator.name,
            "email": meeting.creator.email,
            "work": meeting.creator.work,
        })
        seen_user_ids.add(meeting.creator.users_id)

    meeting_users = MeetingUsers.objects.filter(meeting=meeting).select_related("user")
    for meeting_user in meeting_users:
        user = meeting_user.user
        if user.users_id in seen_user_ids:
            continue
        participants.append({
            "meeting_users_id": meeting_user.meeting_users_id,
            "user_id": user.users_id,
            "name": user.name,
            "email": user.email,
            "work": user.work,
        })
        seen_user_ids.add(user.users_id)

    return participants


class MeetingSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    is_meeting = serializers.SerializerMethodField()
    elapsed_seconds = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = "__all__"

    def get_status(self, obj):
        return {
            Meeting.MeetingStatus.SCHEDULED:   "scheduled",
            Meeting.MeetingStatus.IN_PROGRESS: "in_progress",
            Meeting.MeetingStatus.FINISHED:    "finished",
        }.get(obj.meeting_status, "scheduled")

    def get_is_meeting(self, obj):
        return obj.meeting_status == Meeting.MeetingStatus.IN_PROGRESS

    def get_elapsed_seconds(self, obj):
        from django.utils import timezone
        if obj.meeting_status == Meeting.MeetingStatus.IN_PROGRESS and not obj.is_paused and obj.meeting_at:
            delta = timezone.now() - obj.meeting_at
            try:
                curr_sec = int(obj.during_time or "0")
            except ValueError:
                curr_sec = 0
            return curr_sec + int(delta.total_seconds())
        try:
            return int(obj.during_time or "0")
        except ValueError:
            return 0

    def get_creator_name(self, obj):
        return obj.creator.name if obj.creator else None

    def get_participants(self, obj):
        return build_meeting_participants(obj)


class MeetingAgendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingAgendas
        fields = "__all__"


class MeetingTaskSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()

    class Meta:
        model = MeetingTask
        fields = "__all__"

    def get_owner(self, obj):
        if obj.meeting_users and obj.meeting_users.user:
            return obj.meeting_users.user.name
        return ""


class MeetingUsersSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingUsers
        fields = "__all__"


class RecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Record
        fields = "__all__"

class RecordUtteranceSerializer(serializers.ModelSerializer):
    meeting_user_name = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()

    class Meta:
        model = RecordUtterance
        fields = "__all__"

    def get_meeting_user_name(self, obj):
        if obj.meeting_users and obj.meeting_users.user:
            return obj.meeting_users.user.name
        return ""

    def get_user_id(self, obj):
        if obj.meeting_users and obj.meeting_users.user:
            return obj.meeting_users.user.users_id
        return None


from .models import MeetingPreparation

class MeetingPreparationSerializer(serializers.ModelSerializer):
    sources = serializers.SerializerMethodField()
    effect = serializers.SerializerMethodField()

    class Meta:
        model = MeetingPreparation
        fields = "__all__"

    def get_effect(self, obj):
        if not obj.effect:
            return ""
        if "\n\n__RAW_SOURCES__\n" in obj.effect:
            return obj.effect.split("\n\n__RAW_SOURCES__\n", 1)[0]
        return obj.effect

    def get_sources(self, obj):
        from apps.meetings.models import PreparationDocument
        from apps.documents.models import Document
        from django.core.files.storage import default_storage

        sources_list = []
        try:
            prep_docs = PreparationDocument.objects.filter(preparation=obj)
            for pd in prep_docs:
                doc = Document.objects.filter(document_id=pd.document_id).first()
                if not doc:
                    continue


                file_url = ""
                if doc.path:
                    try:
                        file_url = default_storage.url(doc.path)
                    except Exception:
                        file_url = ""

                sources_list.append({
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "file_url": file_url,
                })
            return sources_list
        except Exception as e:
            print("Error in get_sources serializer:", e)
            return []

