from datetime import datetime, timedelta
from urllib.parse import quote
import base64
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from openai import OpenAI

from .forms import StudentForm, ensure_grade_settings

from .models import (
    AIConversation,
    AIMessage,
    AvailableSubject,
    Exam,
    ExamResult,
    GradeSetting,
    Homework,
    HomeworkAnswer,
    HomeworkResult,
    HomeworkSubmission,
    Lesson,
    LessonWatchStat,
    PasswordResetOTP,
    PlatformSettings,
    Skill,
    SkillLesson,
    SkillSubscription,
    SkillHomework,
    SkillHomeworkAnswer,
    SkillHomeworkQuestion,
    SkillHomeworkResult,
    SkillHomeworkSubmission,
    Student,
    SubjectSubscription,
    SubscriptionRequest,
    TeacherQuestion,
    TeacherReply,
)


# =========================================================
# إعدادات عامة
# =========================================================

DJANGO_BACKEND = "django.contrib.auth.backends.ModelBackend"

SUPPORT_WHATSAPP = "01555266046"

MAX_AI_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_AI_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_TEACHER_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_TEACHER_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_TEACHER_AUDIO_SIZE = 20 * 1024 * 1024

PASSWORD_RESET_MAX_ATTEMPTS = 5
PASSWORD_RESET_CODE_MINUTES = 10
PASSWORD_RESET_RESEND_SECONDS = 60


# =========================================================
# أدوات مساعدة
# =========================================================

def get_current_student(request):
    if not request.user.is_authenticated:
        return None

    return (
        Student.objects
        .filter(user=request.user)
        .select_related("user")
        .first()
    )


def get_platform_settings():
    return PlatformSettings.get_settings()


def is_curriculum_open(settings_obj):
    return settings_obj.curriculum_is_open_now()


def is_skills_open(settings_obj):
    return settings_obj.skills_are_open_now()


def build_whatsapp_link(number):
    if not number:
        return "#"

    digits = "".join(
        char
        for char in str(number)
        if char.isdigit()
    )

    if digits.startswith("0"):
        digits = "20" + digits[1:]

    return f"https://wa.me/{digits}"


def mask_email(email):
    """
    إخفاء جزء من البريد الإلكتروني عند عرضه للطالب.
    مثال:
    samasemo@gmail.com
    تصبح:
    s*****@gmail.com
    """

    email = (email or "").strip()

    if "@" not in email:
        return ""

    username, domain = email.split(
        "@",
        1,
    )

    if not username:
        return f"***@{domain}"

    if len(username) == 1:
        masked_username = "*"
    elif len(username) == 2:
        masked_username = (
            username[0]
            + "*"
        )
    else:
        masked_username = (
            username[0]
            + "*" * min(
                len(username) - 1,
                5,
            )
        )

    return (
        f"{masked_username}@{domain}"
    )


def clear_password_reset_session(request):
    request.session.pop(
        "password_reset_student_id",
        None,
    )

    request.session.pop(
        "password_reset_verified",
        None,
    )

    request.session.pop(
        "password_reset_sent_at",
        None,
    )


# =========================================================
# اشتراكات الطالب
# =========================================================

def get_student_subject_subscriptions(student):
    subscriptions = (
        SubjectSubscription.objects
        .filter(
            student=student,
            is_active=True,
        )
        .order_by("subject")
    )

    usable = []

    for subscription in subscriptions:
        subscription.check_expired()

        if subscription.is_usable:
            usable.append(subscription)

    return usable


def get_student_subjects(student):
    subscriptions = get_student_subject_subscriptions(student)

    return [
        subscription.subject
        for subscription in subscriptions
    ]


def get_student_subject_cards(student):
    subscriptions = get_student_subject_subscriptions(student)

    cards = []

    for subscription in subscriptions:
        cards.append(
            {
                "name": subscription.subject,
                "plan_type": subscription.plan_type,
                "remaining": subscription.lessons_remaining,
                "subscription": subscription,
            }
        )

    return cards


def get_student_skill_subscriptions(student):
    subscriptions = (
        SkillSubscription.objects
        .filter(
            student=student,
            is_active=True,
            skill__is_active=True,
        )
        .select_related("skill")
        .order_by("skill__name")
    )

    return list(subscriptions)


def get_student_skills(student):
    subscriptions = get_student_skill_subscriptions(student)

    return [
        subscription.skill
        for subscription in subscriptions
    ]


# =========================================================
# تقدم المنهج
# =========================================================

def get_subject_progress_data(student):
    """
    تجهيز بيانات المنهج لكل مادة مشترَك فيها:

    - عدد الحصص الكلي
    - عدد الحصص المشاهدة
    - عدد الحصص غير المشاهدة
    - أسماء الحصص
    - حالة الواجب لكل حصة
    - نتائج الواجبات
    - نتائج الامتحانات
    - هل المادة انتهت أم لا
    """

    subscriptions = (
        SubjectSubscription.objects
        .filter(
            student=student,
            is_active=True,
        )
        .order_by("subject")
    )

    data = []

    for subscription in subscriptions:
        subscription.check_expired()

        if not subscription.is_active:
            continue

        lessons = list(
            Lesson.objects
            .filter(
                grade=student.grade,
                school_type=student.school_type,
                subject=subscription.subject,
                is_active=True,
            )
            .order_by("created_at", "id")
        )

        lesson_ids = [
            lesson.id
            for lesson in lessons
        ]

        watch_stats = {
            stat.lesson_id: stat
            for stat in (
                LessonWatchStat.objects
                .filter(
                    student=student,
                    lesson_id__in=lesson_ids,
                )
            )
        }

        homeworks = list(
            Homework.objects
            .filter(
                grade=student.grade,
                school_type=student.school_type,
                subject=subscription.subject,
                is_active=True,
            )
            .order_by("created_at", "id")
        )

        homework_ids = [
            homework.id
            for homework in homeworks
        ]

        submissions = {
            submission.homework_id: submission
            for submission in (
                HomeworkSubmission.objects
                .filter(
                    student=student,
                    homework_id__in=homework_ids,
                )
            )
        }

        homework_results = {
            result.homework_id: result
            for result in (
                HomeworkResult.objects
                .filter(
                    student=student,
                    homework_id__in=homework_ids,
                )
            )
        }

        exams = list(
            Exam.objects
            .filter(
                grade=student.grade,
                school_type=student.school_type,
                subject=subscription.subject,
                is_active=True,
            )
            .order_by("created_at", "id")
        )

        exam_ids = [
            exam.id
            for exam in exams
        ]

        exam_results = {
            result.exam_id: result
            for result in (
                ExamResult.objects
                .filter(
                    student=student,
                    exam_id__in=exam_ids,
                )
            )
        }

        lesson_data = []

        watched_count = 0
        unwatched_count = 0

        for lesson in lessons:
            stat = watch_stats.get(lesson.id)

            is_watched = bool(
                stat
                and (
                    stat.view_count > 0
                    or stat.watch_seconds > 0
                )
            )

            if is_watched:
                watched_count += 1
            else:
                unwatched_count += 1

            related_homeworks = [
                homework
                for homework in homeworks
                if getattr(
                    homework,
                    "lesson_id",
                    None,
                ) == lesson.id
            ]

            lesson_homeworks = []

            for homework in related_homeworks:
                submission = submissions.get(
                    homework.id
                )

                result = homework_results.get(
                    homework.id
                )

                lesson_homeworks.append(
                    {
                        "homework": homework,
                        "submission": submission,
                        "result": result,
                        "submitted": bool(
                            submission
                            and submission.status
                            in [
                                "submitted",
                                "graded",
                            ]
                        ),
                    }
                )

            lesson_data.append(
                {
                    "lesson": lesson,
                    "is_watched": is_watched,
                    "watch_stat": stat,
                    "homeworks": lesson_homeworks,
                }
            )

        # واجبات غير مرتبطة بحصة
        unlinked_homeworks = []

        for homework in homeworks:
            if getattr(
                homework,
                "lesson_id",
                None,
            ):
                continue

            submission = submissions.get(
                homework.id
            )

            result = homework_results.get(
                homework.id
            )

            unlinked_homeworks.append(
                {
                    "homework": homework,
                    "submission": submission,
                    "result": result,
                    "submitted": bool(
                        submission
                        and submission.status
                        in [
                            "submitted",
                            "graded",
                        ]
                    ),
                }
            )

        total_homework_count = len(
            homeworks
        )

        submitted_homework_count = sum(
            1
            for submission in submissions.values()
            if submission.status
            in [
                "submitted",
                "graded",
            ]
        )

        homework_remaining_count = max(
            total_homework_count
            - submitted_homework_count,
            0,
        )

        total_exam_count = len(exams)

        completed_exam_count = sum(
            1
            for exam_id in exam_ids
            if exam_id in exam_results
        )

        remaining_lessons = (
            subscription.lessons_remaining
        )

        if subscription.plan_type == "full_term":
            subject_finished = (
                len(lessons) > 0
                and unwatched_count == 0
            )
        else:
            subject_finished = (
                remaining_lessons == 0
            )

        data.append(
            {
                "subscription": subscription,
                "subject": subscription.subject,
                "plan_type": subscription.plan_type,

                "lessons": lessons,
                "lesson_data": lesson_data,

                "total_lessons": len(lessons),
                "watched_lessons": watched_count,
                "unwatched_lessons": unwatched_count,

                "remaining_lessons": remaining_lessons,

                "homeworks": homeworks,
                "unlinked_homeworks": unlinked_homeworks,

                "total_homeworks": total_homework_count,
                "submitted_homeworks": submitted_homework_count,
                "remaining_homeworks": homework_remaining_count,

                "homework_results": list(
                    homework_results.values()
                ),

                "exams": exams,
                "exam_results": list(
                    exam_results.values()
                ),

                "total_exams": total_exam_count,
                "completed_exams": completed_exam_count,

                "subject_finished": subject_finished,
            }
        )

    return data


# =========================================================
# تقدم المهارات
# =========================================================

def get_skill_progress_data(student):
    """
    تجهيز تقدم كل مهارة للطالب:

    - الحصص المشاهدة
    - الحصص غير المشاهدة
    - الواجبات
    - هل الواجب تم تسليمه أم لا
    - نتائج الواجبات
    """

    subscriptions = (
        SkillSubscription.objects
        .filter(
            student=student,
            is_active=True,
            skill__is_active=True,
        )
        .select_related("skill")
        .order_by("skill__name")
    )

    data = []

    for subscription in subscriptions:
        skill = subscription.skill

        lessons = list(
            SkillLesson.objects
            .filter(
                skill=skill,
                is_active=True,
            )
            .order_by("order", "id")
        )

        lesson_ids = [
            lesson.id
            for lesson in lessons
        ]

        watched_skill_lessons = set()

        if lesson_ids:
            try:
                skill_stats = (
                    LessonWatchStat.objects
                    .filter(
                        student=student,
                        lesson_id__in=lesson_ids,
                    )
                )

                for stat in skill_stats:
                    if (
                        stat.view_count > 0
                        or stat.watch_seconds > 0
                    ):
                        watched_skill_lessons.add(
                            stat.lesson_id
                        )

            except Exception:
                watched_skill_lessons = set()

        skill_homeworks = list(
            SkillHomework.objects
            .filter(
                skill=skill,
                is_active=True,
            )
            .prefetch_related("questions")
            .order_by("created_at", "id")
        )

        homework_ids = [
            homework.id
            for homework in skill_homeworks
        ]

        submissions = {
            submission.homework_id: submission
            for submission in (
                SkillHomeworkSubmission.objects
                .filter(
                    student=student,
                    homework_id__in=homework_ids,
                )
            )
        }

        results = {
            result.homework_id: result
            for result in (
                SkillHomeworkResult.objects
                .filter(
                    student=student,
                    homework_id__in=homework_ids,
                )
            )
        }

        lesson_data = []

        watched_count = 0
        unwatched_count = 0

        for lesson in lessons:
            is_watched = (
                lesson.id
                in watched_skill_lessons
            )

            if is_watched:
                watched_count += 1
            else:
                unwatched_count += 1

            related_homeworks = [
                homework
                for homework in skill_homeworks
                if getattr(
                    homework,
                    "lesson_id",
                    None,
                ) == lesson.id
            ]

            lesson_homeworks = []

            for homework in related_homeworks:
                submission = submissions.get(
                    homework.id
                )

                result = results.get(
                    homework.id
                )

                lesson_homeworks.append(
                    {
                        "homework": homework,
                        "submission": submission,
                        "result": result,
                        "submitted": bool(
                            submission
                            and submission.status
                            in [
                                "submitted",
                                "graded",
                            ]
                        ),
                    }
                )

            lesson_data.append(
                {
                    "lesson": lesson,
                    "is_watched": is_watched,
                    "homeworks": lesson_homeworks,
                }
            )

        submitted_count = sum(
            1
            for submission in submissions.values()
            if submission.status
            in [
                "submitted",
                "graded",
            ]
        )

        total_homework_count = len(
            skill_homeworks
        )

        remaining_homework_count = max(
            total_homework_count
            - submitted_count,
            0,
        )

        data.append(
            {
                "subscription": subscription,
                "skill": skill,

                "lessons": lessons,
                "lesson_data": lesson_data,

                "total_lessons": len(lessons),
                "watched_lessons": watched_count,
                "unwatched_lessons": unwatched_count,

                "homeworks": skill_homeworks,

                "total_homeworks": (
                    total_homework_count
                ),
                "submitted_homeworks": (
                    submitted_count
                ),
                "remaining_homeworks": (
                    remaining_homework_count
                ),

                "submissions": submissions,
                "results": results,
            }
        )

    return data


# =========================================================
# المواد المتاحة
# =========================================================

def get_available_subjects(student):
    setting = (
        GradeSetting.objects
        .filter(
            grade=student.grade,
            is_active=True,
        )
        .first()
    )

    if not setting:
        return AvailableSubject.objects.none()

    active_subjects = set(
        get_student_subjects(student)
    )

    return (
        AvailableSubject.objects
        .filter(
            grade=setting,
            school_type=student.school_type,
            is_active=True,
        )
        .exclude(
            subject_name__in=active_subjects
        )
        .order_by("subject_name")
    )


def get_available_skills(student):
    active_skill_ids = (
        SkillSubscription.objects
        .filter(
            student=student,
            is_active=True,
        )
        .values_list(
            "skill_id",
            flat=True,
        )
    )

    return (
        Skill.objects
        .filter(is_active=True)
        .exclude(id__in=active_skill_ids)
        .prefetch_related("prerequisites")
        .order_by("name")
    )


# =========================================================
# أسعار المواد
# =========================================================

def get_subject_monthly_price(student, subject_obj):
    if not subject_obj:
        return 0

    return subject_obj.monthly_price or 0


def get_subject_full_term_price(student, subject_obj):
    if not subject_obj:
        return 0

    return subject_obj.full_term_price or 0


def get_subject_price_data(student, subjects):
    data = []

    for subject in subjects:
        data.append(
            {
                "subject": subject,
                "monthly_price": get_subject_monthly_price(
                    student,
                    subject,
                ),
                "full_term_price": get_subject_full_term_price(
                    student,
                    subject,
                ),
            }
        )

    return data


# =========================================================
# طلبات الاشتراك
# =========================================================

def get_latest_request(student):
    return (
        SubscriptionRequest.objects
        .filter(student=student)
        .order_by("-created_at")
        .first()
    )


def get_latest_pending_request(student):
    return (
        SubscriptionRequest.objects
        .filter(
            student=student,
            status="pending",
        )
        .order_by("-created_at")
        .first()
    )


def get_latest_rejected_request(student):
    return (
        SubscriptionRequest.objects
        .filter(
            student=student,
            status="rejected",
        )
        .order_by("-created_at")
        .first()
    )


def render_old_student(
    request,
    student_obj=None,
    error=None,
    rejected_request=None,
    show_subscription=False,
):
    settings_obj = get_platform_settings()

    return render(
        request,
        "main/old_student.html",
        {
            "student": student_obj,
            "error": error,
            "rejected_request": rejected_request,
            "show_subscription": show_subscription,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
            "vodafone_number": (
                settings_obj.vodafone_cash_number
            ),
        },
    )


# =========================================================
# Home
# =========================================================

def home(request):
    return render(
        request,
        "main/manasa.html",
    )


# =========================================================
# طالب جديد
# =========================================================

def student(request):
    ensure_grade_settings()

    settings_obj = get_platform_settings()

    active_grades = (
        GradeSetting.objects
        .filter(is_active=True)
        .order_by("id")
    )

    skills = (
        Skill.objects
        .filter(is_active=True)
        .prefetch_related("prerequisites")
        .order_by("name")
    )

    if request.method == "POST":
        form = StudentForm(request.POST)

        password = request.POST.get(
            "password",
            "",
        )

        confirm_password = request.POST.get(
            "confirmPassword",
            "",
        )

        context = {
            "form": form,
            "success": False,
            "skills": skills,
            "active_grades": active_grades,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        }

        if password != confirm_password:
            form.add_error(
                None,
                "كلمتا المرور غير متطابقتين.",
            )

            return render(
                request,
                "main/student.html",
                context,
            )

        if len(password) < 6:
            form.add_error(
                None,
                "كلمة المرور يجب أن تكون 6 أحرف أو أرقام على الأقل.",
            )

            return render(
                request,
                "main/student.html",
                context,
            )

        if form.is_valid():
            student_phone = (
                form.cleaned_data["student_phone"]
                .strip()
            )

            existing_student = (
                Student.objects
                .filter(
                    student_phone=student_phone
                )
                .first()
            )

            if existing_student:
                form.add_error(
                    "student_phone",
                    "رقم تليفون الطالب مسجل بالفعل.",
                )

                return render(
                    request,
                    "main/student.html",
                    context,
                )

            existing_user = (
                User.objects
                .filter(
                    username=student_phone
                )
                .first()
            )

            if existing_user:
                linked_student = (
                    Student.objects
                    .filter(
                        user=existing_user
                    )
                    .first()
                )

                if linked_student:
                    form.add_error(
                        "student_phone",
                        "هذا الرقم مرتبط بحساب طالب موجود بالفعل.",
                    )

                    return render(
                        request,
                        "main/student.html",
                        context,
                    )

                if (
                    existing_user.is_staff
                    or existing_user.is_superuser
                ):
                    form.add_error(
                        "student_phone",
                        "هذا الرقم مرتبط بحساب إداري ولا يمكن استخدامه.",
                    )

                    return render(
                        request,
                        "main/student.html",
                        context,
                    )

                existing_user.delete()

            selected_skills = (
                form.cleaned_data.get(
                    "initial_skills"
                )
                or []
            )

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=student_phone,
                        password=password,
                    )

                    user.is_active = True

                    user.save(
                        update_fields=[
                            "is_active"
                        ]
                    )

                    student_obj = form.save(
                        commit=False
                    )

                    student_obj.user = user
                    student_obj.is_active = False

                    student_obj.selected_skills = [
                        skill.name
                        for skill in selected_skills
                    ]

                    student_obj.save()

                login(
                    request,
                    user,
                    backend=DJANGO_BACKEND,
                )

                messages.success(
                    request,
                    "تم إنشاء حساب الطالب بنجاح ✅",
                )

                return redirect(
                    "subscription"
                )

            except Exception as exc:
                print(
                    "Student registration error:",
                    exc,
                )

                form.add_error(
                    None,
                    "حدث خطأ أثناء إنشاء الحساب. حاولي مرة أخرى.",
                )

    else:
        form = StudentForm()

    return render(
        request,
        "main/student.html",
        {
            "form": form,
            "success": False,
            "skills": skills,
            "active_grades": active_grades,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# Subscription
# =========================================================

@login_required
def subscription(request):
    student_obj = get_current_student(request)

    if not student_obj:
        return redirect("student")

    ensure_grade_settings()

    settings_obj = get_platform_settings()

    curriculum_open = is_curriculum_open(
        settings_obj
    )

    skills_open = is_skills_open(
        settings_obj
    )

    available_subjects = list(
        get_available_subjects(
            student_obj
        )
    )

    available_skills = list(
        get_available_skills(
            student_obj
        )
    )

    subject_price_data = get_subject_price_data(
        student_obj,
        available_subjects,
    )

    pending_request = get_latest_pending_request(
        student_obj
    )

    rejected_request = get_latest_rejected_request(
        student_obj
    )

    default_selected_skills = (
        student_obj.selected_skills
        if isinstance(
            student_obj.selected_skills,
            list,
        )
        else []
    )

    common_context = {
        "student": student_obj,
        "available_subjects": available_subjects,
        "subject_price_data": subject_price_data,
        "available_skills": available_skills,
        "curriculum_open": curriculum_open,
        "skills_open": skills_open,
        "vodafone_number": settings_obj.vodafone_cash_number,
        "support_whatsapp": build_whatsapp_link(
            settings_obj.whatsapp_number
        ),
        "pending_request": pending_request,
        "rejected_request": rejected_request,
        "selected_subjects": [],
        "selected_skills": default_selected_skills,
        "plan": "monthly",
        "total_amount": 0,
    }

    if request.method == "POST":
        if pending_request:
            common_context["error"] = (
                "لديك طلب اشتراك قيد المراجعة بالفعل."
            )

            return render(
                request,
                "main/subscription.html",
                common_context,
            )

        plan = request.POST.get(
            "plan",
            "monthly",
        ).strip()

        if plan not in [
            "monthly",
            "full_term",
            "skills",
            "mixed",
        ]:
            plan = "monthly"

        selected_subjects = list(
            dict.fromkeys(
                request.POST.getlist(
                    "selected_subjects"
                )
            )
        )

        posted_skill_values = list(
            dict.fromkeys(
                request.POST.getlist(
                    "selected_skills"
                )
            )
        )

        transfer_image = request.FILES.get(
            "transfer_image"
        )

        common_context["plan"] = plan
        common_context["selected_subjects"] = (
            selected_subjects
        )
        common_context["selected_skills"] = (
            posted_skill_values
        )

        if not transfer_image:
            common_context["error"] = (
                "من فضلك ارفعي صورة التحويل."
            )

            return render(
                request,
                "main/subscription.html",
                common_context,
            )

        available_subject_map = {
            subject.subject_name: subject
            for subject in available_subjects
        }

        selected_subjects = [
            subject_name
            for subject_name in selected_subjects
            if subject_name in available_subject_map
        ]

        if (
            selected_subjects
            and not curriculum_open
        ):
            common_context["error"] = (
                "المنهج غير متاح حاليًا."
            )

            return render(
                request,
                "main/subscription.html",
                common_context,
            )

        available_skill_map_by_id = {
            str(skill.id): skill
            for skill in available_skills
        }

        available_skill_map_by_name = {
            skill.name: skill
            for skill in available_skills
        }

        selected_skill_objects = []

        for value in posted_skill_values:
            skill = (
                available_skill_map_by_id.get(
                    str(value)
                )
                or available_skill_map_by_name.get(
                    str(value)
                )
            )

            if skill:
                selected_skill_objects.append(
                    skill
                )

        selected_skill_objects = list(
            {
                skill.id: skill
                for skill in selected_skill_objects
            }.values()
        )

        selected_skills = [
            skill.name
            for skill in selected_skill_objects
        ]

        common_context["selected_skills"] = (
            selected_skills
        )

        if (
            selected_skills
            and not skills_open
        ):
            common_context["error"] = (
                "المهارات غير متاحة حاليًا."
            )

            return render(
                request,
                "main/subscription.html",
                common_context,
            )

        if plan == "skills":
            selected_subjects = []

        elif plan == "full_term":
            pass

        if (
            not selected_subjects
            and not selected_skills
        ):
            common_context["error"] = (
                "اختاري مادة أو مهارة واحدة على الأقل."
            )

            return render(
                request,
                "main/subscription.html",
                common_context,
            )

        curriculum_amount = 0

        for subject_name in selected_subjects:
            subject_obj = available_subject_map.get(
                subject_name
            )

            if not subject_obj:
                continue

            if plan == "full_term":
                curriculum_amount += (
                    get_subject_full_term_price(
                        student_obj,
                        subject_obj,
                    )
                )
            else:
                curriculum_amount += (
                    get_subject_monthly_price(
                        student_obj,
                        subject_obj,
                    )
                )

        skills_amount = 0

        selected_skill_names = set(
            selected_skills
        )

        for skill in selected_skill_objects:
            missing_prerequisites = []

            for prerequisite in (
                skill.prerequisites.all()
            ):
                already_active = (
                    SkillSubscription.objects
                    .filter(
                        student=student_obj,
                        skill=prerequisite,
                        is_active=True,
                    )
                    .exists()
                )

                if (
                    prerequisite.name
                    not in selected_skill_names
                    and not already_active
                ):
                    missing_prerequisites.append(
                        prerequisite.name
                    )

            if missing_prerequisites:
                common_context["error"] = (
                    f"المهارة {skill.name} تحتاج أولًا إلى: "
                    + " + ".join(
                        missing_prerequisites
                    )
                )

                return render(
                    request,
                    "main/subscription.html",
                    common_context,
                )

            skills_amount += skill.course_price

        amount = (
            curriculum_amount
            + skills_amount
        )

        if (
            selected_subjects
            and selected_skills
        ):
            final_type = "mixed"

        elif selected_skills:
            final_type = "skills"

        elif plan == "full_term":
            final_type = "full_term"

        else:
            final_type = "subjects"

        common_context["selected_subjects"] = (
            selected_subjects
        )

        common_context["selected_skills"] = (
            selected_skills
        )

        common_context["total_amount"] = amount

        SubscriptionRequest.objects.create(
            student=student_obj,
            request_type="initial",
            amount=amount,
            curriculum_amount=curriculum_amount,
            skills_amount=skills_amount,
            subscription_type=final_type,
            selected_subjects=selected_subjects,
            selected_skills=selected_skills,
            transfer_image=transfer_image,
            status="pending",
        )

        return render(
            request,
            "main/subscription.html",
            {
                **common_context,
                "success": True,
                "amount": amount,
            },
        )

    return render(
        request,
        "main/subscription.html",
        common_context,
    )


# =========================================================
# Old Student
# =========================================================

def old_student(request):
    if request.method != "POST":
        return render_old_student(request)

    phone = (
        request.POST.get(
            "student_phone",
            "",
        )
        .strip()
    )

    password = request.POST.get(
        "password",
        "",
    )

    student_obj = (
        Student.objects
        .filter(student_phone=phone)
        .select_related("user")
        .first()
    )

    if not student_obj:
        return render_old_student(
            request,
            error=(
                "لا يوجد حساب بهذا الرقم. "
                "يمكنك إنشاء حساب طالب جديد."
            ),
        )

    if not student_obj.user:
        return render_old_student(
            request,
            student_obj=student_obj,
            error=(
                "الحساب غير مكتمل. "
                "تواصلي مع الإدارة."
            ),
        )

    user = authenticate(
        request,
        username=student_obj.user.username,
        password=password,
        backend=DJANGO_BACKEND,
    )

    if user is None:
        return render_old_student(
            request,
            student_obj=student_obj,
            error="كلمة المرور غير صحيحة.",
        )

    login(
        request,
        user,
        backend=DJANGO_BACKEND,
    )

    if student_obj.is_active:
        return redirect(
            "student_dashboard"
        )

    pending_request = get_latest_pending_request(
        student_obj
    )

    if pending_request:
        return render_old_student(
            request,
            student_obj=student_obj,
            error=(
                "طلب الاشتراك الخاص بك قيد المراجعة حاليًا."
            ),
        )

    rejected_request = get_latest_rejected_request(
        student_obj
    )

    if rejected_request:
        return render_old_student(
            request,
            student_obj=student_obj,
            rejected_request=rejected_request,
            show_subscription=False,
        )

    if student_obj.suspension_reason:
        return render_old_student(
            request,
            student_obj=student_obj,
            error=(
                "تم إيقاف الحساب حاليًا.\n\n"
                f"السبب: {student_obj.suspension_reason}"
            ),
        )

    return redirect(
        "old_student_subscription"
    )


# =========================================================
# Old Student Subscription
# =========================================================

@login_required
def old_student_subscription(request):
    student_obj = get_current_student(request)

    if not student_obj:
        return redirect("old_student")

    if student_obj.is_active:
        return redirect("student_dashboard")

    ensure_grade_settings()

    settings_obj = get_platform_settings()

    active_grades = (
        GradeSetting.objects
        .filter(is_active=True)
        .order_by("id")
    )

    selected_grade = request.POST.get(
        "grade",
        request.GET.get(
            "grade",
            student_obj.grade or "",
        ),
    ).strip()

    selected_school_type = request.POST.get(
        "school_type",
        request.GET.get(
            "school_type",
            student_obj.school_type or "",
        ),
    ).strip()

    grade_setting = (
        GradeSetting.objects
        .filter(
            grade=selected_grade,
            is_active=True,
        )
        .first()
    )

    available_subjects = (
        AvailableSubject.objects
        .filter(
            grade=grade_setting,
            school_type=selected_school_type,
            is_active=True,
        )
        .order_by("subject_name")
        if grade_setting
        else AvailableSubject.objects.none()
    )

    subject_price_data = get_subject_price_data(
        student_obj,
        available_subjects,
    )

    context = {
        "student": student_obj,
        "grades": active_grades,
        "selected_grade": selected_grade,
        "selected_school_type": selected_school_type,
        "available_subjects": available_subjects,
        "subject_price_data": subject_price_data,
        "vodafone_number": (
            settings_obj.vodafone_cash_number
        ),
        "support_whatsapp": build_whatsapp_link(
            settings_obj.whatsapp_number
        ),
    }

    if request.method == "POST":
        if not selected_grade:
            context["error"] = "اختاري الصف أولًا."

            return render(
                request,
                "main/old_student_subscription.html",
                context,
            )

        if not grade_setting:
            context["error"] = (
                "هذا الصف غير متاح حاليًا."
            )

            return render(
                request,
                "main/old_student_subscription.html",
                context,
            )

        if selected_school_type not in [
            "عربي",
            "لغات",
        ]:
            context["error"] = (
                "اختاري نوع التعليم."
            )

            return render(
                request,
                "main/old_student_subscription.html",
                context,
            )

        student_obj.grade = selected_grade
        student_obj.school_type = selected_school_type

        student_obj.save(
            update_fields=[
                "grade",
                "school_type",
                "updated_at",
            ]
        )

        return redirect(
            "subscription"
        )

    return render(
        request,
        "main/old_student_subscription.html",
        context,
    )


# =========================================================
# Logout
# =========================================================

def student_logout(request):
    logout(request)
    return redirect("home")


# =========================================================
# Student Dashboard
# =========================================================

@login_required
def student_dashboard(request):
    student_obj = get_current_student(request)

    if not student_obj:
        return redirect("student")

    settings_obj = get_platform_settings()

    if not student_obj.is_active:
        pending_request = get_latest_pending_request(
            student_obj
        )

        return render(
            request,
            "main/student_dashboard.html",
            {
                "student": student_obj,
                "pending_request": pending_request,
                "subjects": [],
                "skills": [],
                "curriculum_open": False,
                "skills_open": False,
                "vacation": False,
                "support_whatsapp": build_whatsapp_link(
                    settings_obj.whatsapp_number
                ),
            },
        )

    curriculum_open = is_curriculum_open(
        settings_obj
    )

    skills_open = is_skills_open(
        settings_obj
    )

    subjects = get_student_subject_cards(
        student_obj
    )

    skills = get_student_skill_subscriptions(
        student_obj
    )

    curriculum_progress = (
        get_subject_progress_data(
            student_obj
        )
    )

    skills_progress = (
        get_skill_progress_data(
            student_obj
        )
    )

    return render(
        request,
        "main/student_dashboard.html",
        {
            "student": student_obj,
            "subjects": subjects,
            "skills": skills,

            "curriculum_progress": (
                curriculum_progress
            ),
            "skills_progress": (
                skills_progress
            ),

            "curriculum_open": curriculum_open,
            "skills_open": skills_open,
            "vacation": settings_obj.is_vacation_now(),
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# Curriculum Page
# =========================================================

@login_required
def curriculum_page(request):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    settings_obj = get_platform_settings()

    curriculum_open = is_curriculum_open(
        settings_obj
    )

    subjects = get_student_subject_cards(
        student_obj
    )

    progress = get_subject_progress_data(
        student_obj
    )

    return render(
        request,
        "main/curriculum_page.html",
        {
            "student": student_obj,
            "subjects": subjects,

            "progress": progress,
            "curriculum_progress": progress,

            "curriculum_open": curriculum_open,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# Skills Page
# =========================================================

@login_required
def skills_page(request):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    settings_obj = get_platform_settings()

    skills = get_student_skill_subscriptions(
        student_obj
    )

    progress = get_skill_progress_data(
        student_obj
    )

    return render(
        request,
        "main/skills_page.html",
        {
            "student": student_obj,
            "skills": skills,

            "progress": progress,
            "skills_progress": progress,

            "skills_open": is_skills_open(
                settings_obj
            ),
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# Subject Lessons
# =========================================================

@login_required
def subject_lessons(request, subject):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    subscription_obj = (
        SubjectSubscription.objects
        .filter(
            student=student_obj,
            subject=subject,
            is_active=True,
        )
        .first()
    )

    settings_obj = get_platform_settings()

    if not subscription_obj:
        return render(
            request,
            "main/subject_lessons.html",
            {
                "student": student_obj,
                "subject": subject,
                "subscription": None,
                "support_whatsapp": build_whatsapp_link(
                    settings_obj.whatsapp_number
                ),
            },
        )

    subscription_obj.check_expired()

    if not subscription_obj.is_usable:
        return render(
            request,
            "main/subject_lessons.html",
            {
                "student": student_obj,
                "subject": subject,
                "subscription": subscription_obj,
                "locked_subject": True,
                "support_whatsapp": build_whatsapp_link(
                    settings_obj.whatsapp_number
                ),
            },
        )

    section = request.GET.get(
        "section",
        "lessons",
    )

    lessons = (
        Lesson.objects
        .filter(
            grade=student_obj.grade,
            school_type=student_obj.school_type,
            subject=subject,
            is_active=True,
        )
        .order_by("created_at", "id")
    )

    homeworks = (
        Homework.objects
        .filter(
            grade=student_obj.grade,
            school_type=student_obj.school_type,
            subject=subject,
            is_active=True,
        )
        .order_by("-created_at", "-id")
    )

    exams = (
        Exam.objects
        .filter(
            grade=student_obj.grade,
            school_type=student_obj.school_type,
            subject=subject,
            is_active=True,
        )
        .order_by("-created_at", "-id")
    )

    homework_results = (
        HomeworkResult.objects
        .filter(
            student=student_obj,
            homework__subject=subject,
        )
        .select_related("homework")
        .order_by("-created_at")
    )

    exam_results = (
        ExamResult.objects
        .filter(
            student=student_obj,
            exam__subject=subject,
        )
        .select_related("exam")
        .order_by("-created_at")
    )

    submissions = {
        submission.homework_id: submission
        for submission in (
            HomeworkSubmission.objects
            .filter(
                student=student_obj,
                homework__subject=subject,
            )
        )
    }

    lesson_watch_stats = {
        stat.lesson_id: stat
        for stat in (
            LessonWatchStat.objects
            .filter(
                student=student_obj,
                lesson__in=lessons,
            )
        )
    }

    lesson_progress = []

    for lesson in lessons:
        stat = lesson_watch_stats.get(
            lesson.id
        )

        is_watched = bool(
            stat
            and (
                stat.view_count > 0
                or stat.watch_seconds > 0
            )
        )

        related_homeworks = []

        for homework in homeworks:
            if getattr(
                homework,
                "lesson_id",
                None,
            ) == lesson.id:
                related_homeworks.append(
                    {
                        "homework": homework,
                        "submission": submissions.get(
                            homework.id
                        ),
                        "submitted": bool(
                            submissions.get(
                                homework.id
                            )
                            and submissions.get(
                                homework.id
                            ).status
                            in [
                                "submitted",
                                "graded",
                            ]
                        ),
                    }
                )

        lesson_progress.append(
            {
                "lesson": lesson,
                "watch_stat": stat,
                "is_watched": is_watched,
                "homeworks": related_homeworks,
            }
        )

    remaining_lessons = (
        subscription_obj.lessons_remaining
    )

    upload_message = None
    upload_error = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "upload_homework":
            homework_id = request.POST.get(
                "homework_id"
            )

            uploaded_file = request.FILES.get(
                "uploaded_file"
            )

            homework = (
                Homework.objects
                .filter(
                    id=homework_id,
                    subject=subject,
                    grade=student_obj.grade,
                    school_type=student_obj.school_type,
                    homework_type="paper",
                    is_active=True,
                )
                .first()
            )

            if not homework:
                upload_error = "الواجب غير موجود."

            elif not uploaded_file:
                upload_error = (
                    "من فضلك اختاري ملف الإجابة."
                )

            else:
                submission, _ = (
                    HomeworkSubmission.objects
                    .get_or_create(
                        student=student_obj,
                        homework=homework,
                    )
                )

                submission.uploaded_file = (
                    uploaded_file
                )

                submission.status = "submitted"

                if hasattr(
                    submission,
                    "submitted_at",
                ):
                    submission.submitted_at = (
                        timezone.now()
                    )

                if hasattr(
                    submission,
                    "graded_at",
                ):
                    submission.graded_at = None

                submission.save()

                submissions[homework.id] = submission

                upload_message = (
                    "تم رفع إجابة الواجب بنجاح ✅"
                )

    return render(
        request,
        "main/subject_lessons.html",
        {
            "student": student_obj,
            "subject": subject,
            "subscription": subscription_obj,
            "section": section,
            "lessons": lessons,
            "homeworks": homeworks,
            "exams": exams,
            "homework_results": homework_results,
            "exam_results": exam_results,
            "remaining_lessons": remaining_lessons,
            "submissions": submissions,

            "lesson_progress": lesson_progress,
            "lesson_watch_stats": lesson_watch_stats,

            "upload_message": upload_message,
            "upload_error": upload_error,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# اسأل مدرس
# =========================================================

@login_required
def ask_teacher(request, lesson_id):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    lesson = get_object_or_404(
        Lesson,
        pk=lesson_id,
        is_active=True,
    )

    subscription_obj = (
        SubjectSubscription.objects
        .filter(
            student=student_obj,
            subject=lesson.subject,
            is_active=True,
        )
        .first()
    )

    if not subscription_obj:
        raise Http404(
            "لا يوجد اشتراك في المادة."
        )

    subscription_obj.check_expired()

    if not subscription_obj.is_usable:
        raise Http404(
            "الاشتراك غير متاح."
        )

    if (
        lesson.grade != student_obj.grade
        or lesson.school_type != student_obj.school_type
    ):
        raise Http404(
            "لا يوجد وصول لهذا الدرس."
        )

    if request.method == "POST":

        message_text = (
            request.POST.get(
                "message",
                "",
            )
            or ""
        ).strip()

        image = request.FILES.get("image")
        audio = request.FILES.get("audio")

        if not message_text and not image and not audio:
            messages.error(
                request,
                "اكتبي سؤالك أو أرفقي صورة أو تسجيلًا صوتيًا.",
            )

            return redirect(
                "ask_teacher",
                lesson_id=lesson.id,
            )

        if image:

            content_type = (
                getattr(
                    image,
                    "content_type",
                    "",
                )
                or ""
            ).lower()

            if content_type not in ALLOWED_TEACHER_IMAGE_TYPES:

                messages.error(
                    request,
                    "من فضلك اختاري صورة بصيغة JPG أو PNG أو WEBP.",
                )

                return redirect(
                    "ask_teacher",
                    lesson_id=lesson.id,
                )

            if image.size > MAX_TEACHER_IMAGE_SIZE:

                messages.error(
                    request,
                    "الصورة كبيرة جدًا. الحد الأقصى 10 ميجابايت.",
                )

                return redirect(
                    "ask_teacher",
                    lesson_id=lesson.id,
                )

        if audio:

            audio_content_type = (
                getattr(
                    audio,
                    "content_type",
                    "",
                )
                or ""
            ).lower()

            audio_name = (
                getattr(
                    audio,
                    "name",
                    "",
                )
                or ""
            ).lower()

            allowed_audio_extensions = (
                ".mp3",
                ".wav",
                ".ogg",
                ".webm",
                ".m4a",
                ".aac",
            )

            valid_audio = (
                audio_content_type.startswith("audio/")
                or audio_name.endswith(
                    allowed_audio_extensions
                )
            )

            if not valid_audio:

                messages.error(
                    request,
                    "ملف التسجيل الصوتي غير مدعوم.",
                )

                return redirect(
                    "ask_teacher",
                    lesson_id=lesson.id,
                )

            if audio.size > MAX_TEACHER_AUDIO_SIZE:

                messages.error(
                    request,
                    "التسجيل الصوتي كبير جدًا. الحد الأقصى 20 ميجابايت.",
                )

                return redirect(
                    "ask_teacher",
                    lesson_id=lesson.id,
                )

        TeacherQuestion.objects.create(
            student=student_obj,
            lesson=lesson,
            message=message_text,
            image=image,
            audio=audio,
            status="pending",
        )

        messages.success(
            request,
            "تم إرسال سؤالك للمدرس بنجاح ✅",
        )

        return redirect(
            "ask_teacher",
            lesson_id=lesson.id,
        )

    questions = (
        TeacherQuestion.objects
        .filter(
            student=student_obj,
            lesson=lesson,
        )
        .prefetch_related("replies")
        .order_by("created_at")
    )

    settings_obj = get_platform_settings()

    return render(
        request,
        "main/ask_teacher.html",
        {
            "student": student_obj,
            "lesson": lesson,
            "subject": lesson.subject,
            "subscription": subscription_obj,
            "questions": questions,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# Protected Lesson Video
# =========================================================

@login_required
def protected_lesson_video(request, lesson_id):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        raise Http404("لا يوجد وصول.")

    lesson = get_object_or_404(
        Lesson,
        pk=lesson_id,
        is_active=True,
    )

    subscription_obj = (
        SubjectSubscription.objects
        .filter(
            student=student_obj,
            subject=lesson.subject,
            is_active=True,
        )
        .first()
    )

    if not subscription_obj:
        raise Http404("لا يوجد اشتراك.")

    subscription_obj.check_expired()

    if not subscription_obj.is_usable:
        raise Http404("الاشتراك غير متاح.")

    if (
        lesson.grade != student_obj.grade
        or lesson.school_type != student_obj.school_type
    ):
        raise Http404("لا يوجد وصول.")

    if not lesson.video:
        raise Http404("الفيديو غير موجود.")

    video_file = lesson.video.open("rb")

    return FileResponse(
        video_file,
        content_type="video/mp4",
    )


# =========================================================
# Lesson Watch Progress
# =========================================================

@login_required
@require_POST
def lesson_watch_progress(request, lesson_id):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return JsonResponse(
            {"success": False},
            status=403,
        )

    lesson = get_object_or_404(
        Lesson,
        pk=lesson_id,
        is_active=True,
    )

    subscription_obj = (
        SubjectSubscription.objects
        .filter(
            student=student_obj,
            subject=lesson.subject,
            is_active=True,
        )
        .first()
    )

    if not subscription_obj:
        return JsonResponse(
            {"success": False},
            status=403,
        )

    subscription_obj.check_expired()

    if not subscription_obj.is_usable:
        return JsonResponse(
            {"success": False},
            status=403,
        )

    try:
        watch_seconds = int(
            request.POST.get(
                "watch_seconds",
                0,
            )
        )

        last_position = float(
            request.POST.get(
                "last_position",
                0,
            )
        )

    except (
        ValueError,
        TypeError,
    ):
        watch_seconds = 0
        last_position = 0.0

    stat, created = (
        LessonWatchStat.objects
        .get_or_create(
            student=student_obj,
            lesson=lesson,
        )
    )

    old_view_count = stat.view_count

    if created:
        stat.view_count = 1
    else:
        stat.view_count += 1

    stat.watch_seconds = max(
        stat.watch_seconds,
        watch_seconds,
    )

    stat.last_position = last_position

    stat.save()

    if (
        old_view_count == 0
        and subscription_obj.max_lessons > 0
        and subscription_obj.watched_lessons
        < subscription_obj.max_lessons
    ):
        subscription_obj.watched_lessons += 1

        subscription_obj.save(
            update_fields=[
                "watched_lessons",
                "updated_at",
            ]
        )

    return JsonResponse(
        {
            "success": True,
            "remaining": (
                subscription_obj.lessons_remaining
            ),
        }
    )


# =========================================================
# Electronic Homework
# =========================================================

@login_required
def electronic_homework(request, homework_id):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    homework = get_object_or_404(
        Homework,
        pk=homework_id,
        homework_type="electronic",
        is_active=True,
    )

    if (
        homework.grade != student_obj.grade
        or homework.school_type != student_obj.school_type
    ):
        raise Http404("لا يوجد وصول.")

    subscription_obj = (
        SubjectSubscription.objects
        .filter(
            student=student_obj,
            subject=homework.subject,
            is_active=True,
        )
        .first()
    )

    if not subscription_obj:
        raise Http404(
            "لا يوجد اشتراك في المادة."
        )

    subscription_obj.check_expired()

    if not subscription_obj.is_usable:
        raise Http404(
            "الاشتراك غير متاح."
        )

    questions = homework.questions.all()

    if request.method == "POST":
        submission, _ = (
            HomeworkSubmission.objects
            .get_or_create(
                student=student_obj,
                homework=homework,
            )
        )

        submission.answers.all().delete()

        score = 0
        max_score = 0

        for question in questions:
            selected_answer = request.POST.get(
                f"question_{question.id}",
                "",
            )

            is_correct = (
                selected_answer
                == question.correct_answer
            )

            mark_obtained = (
                question.mark
                if is_correct
                else 0
            )

            score += mark_obtained
            max_score += question.mark

            HomeworkAnswer.objects.create(
                submission=submission,
                question=question,
                selected_answer=selected_answer,
                is_correct=is_correct,
                mark_obtained=mark_obtained,
            )

        submission.status = "graded"

        if hasattr(
            submission,
            "submitted_at",
        ):
            submission.submitted_at = (
                submission.submitted_at
                or timezone.now()
            )

        if hasattr(
            submission,
            "graded_at",
        ):
            submission.graded_at = timezone.now()

        submission.save()

        result, _ = (
            HomeworkResult.objects
            .get_or_create(
                student=student_obj,
                homework=homework,
            )
        )

        result.score = score
        result.max_score = max_score
        result.feedback = (
            "تم تصحيح الواجب الإلكتروني تلقائيًا."
        )

        result.save()

        percentage = 0

        if max_score > 0:
            percentage = round(
                (score / max_score) * 100,
                1,
            )

        return render(
            request,
            "main/electronic_homework_result.html",
            {
                "student": student_obj,
                "homework": homework,
                "subject": homework.subject,
                "score": score,
                "correct": sum(
                    1
                    for answer in submission.answers.all()
                    if answer.is_correct
                ),
                "total": questions.count(),
                "max_score": max_score,
                "percentage": percentage,
            },
        )

    return render(
        request,
        "main/electronic_homework.html",
        {
            "student": student_obj,
            "homework": homework,
            "questions": questions,
        },
    )


# =========================================================
# Add Content
# =========================================================

@login_required
def add_content(request):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    settings_obj = get_platform_settings()

    curriculum_open = is_curriculum_open(
        settings_obj
    )

    skills_open = is_skills_open(
        settings_obj
    )

    available_subjects = (
        get_available_subjects(student_obj)
        if curriculum_open
        else AvailableSubject.objects.none()
    )

    available_skills = (
        get_available_skills(student_obj)
        if skills_open
        else Skill.objects.none()
    )

    available_subjects_list = list(
        available_subjects
    )

    subject_price_data = get_subject_price_data(
        student_obj,
        available_subjects_list,
    )

    common_context = {
        "student": student_obj,
        "available_subjects": available_subjects_list,
        "subject_price_data": subject_price_data,
        "available_skills": available_skills,
        "curriculum_open": curriculum_open,
        "skills_open": skills_open,
        "support_whatsapp": build_whatsapp_link(
            settings_obj.whatsapp_number
        ),
        "vodafone_number": (
            settings_obj.vodafone_cash_number
        ),
        "plan": "monthly",
        "selected_subjects": [],
        "selected_skills": [],
    }

    if request.method == "POST":
        pending_request = get_latest_pending_request(
            student_obj
        )

        if pending_request:
            common_context["error"] = (
                "لديك طلب إضافة قيد المراجعة بالفعل."
            )

            return render(
                request,
                "main/add_content.html",
                common_context,
            )

        plan = request.POST.get(
            "plan",
            "monthly",
        ).strip()

        if plan not in [
            "monthly",
            "full_term",
        ]:
            plan = "monthly"

        common_context["plan"] = plan

        selected_subjects = list(
            dict.fromkeys(
                request.POST.getlist(
                    "selected_subjects"
                )
            )
        )

        selected_skill_values = list(
            dict.fromkeys(
                request.POST.getlist(
                    "selected_skills"
                )
            )
        )

        transfer_image = request.FILES.get(
            "transfer_image"
        )

        if not transfer_image:
            common_context["error"] = (
                "من فضلك ارفعي صورة التحويل."
            )

            return render(
                request,
                "main/add_content.html",
                common_context,
            )

        available_subject_map = {
            subject.subject_name: subject
            for subject in available_subjects_list
        }

        selected_subjects = [
            subject_name
            for subject_name in selected_subjects
            if subject_name in available_subject_map
        ]

        if (
            selected_subjects
            and not curriculum_open
        ):
            common_context["error"] = (
                "المنهج غير متاح حاليًا."
            )

            return render(
                request,
                "main/add_content.html",
                common_context,
            )

        available_skill_map = {
            str(skill.id): skill
            for skill in available_skills
        }

        selected_skills = []

        for value in selected_skill_values:
            skill = available_skill_map.get(
                str(value)
            )

            if skill:
                selected_skills.append(skill)

        selected_skills = list(
            {
                skill.id: skill
                for skill in selected_skills
            }.values()
        )

        if (
            selected_skills
            and not skills_open
        ):
            common_context["error"] = (
                "المهارات غير متاحة حاليًا."
            )

            return render(
                request,
                "main/add_content.html",
                common_context,
            )

        if (
            not selected_subjects
            and not selected_skills
        ):
            common_context["error"] = (
                "اختاري مادة أو مهارة واحدة على الأقل."
            )

            return render(
                request,
                "main/add_content.html",
                common_context,
            )

        curriculum_amount = 0

        for subject_name in selected_subjects:
            subject_obj = available_subject_map.get(
                subject_name
            )

            if not subject_obj:
                continue

            if plan == "full_term":
                curriculum_amount += (
                    get_subject_full_term_price(
                        student_obj,
                        subject_obj,
                    )
                )
            else:
                curriculum_amount += (
                    get_subject_monthly_price(
                        student_obj,
                        subject_obj,
                    )
                )

        skills_amount = sum(
            skill.course_price
            for skill in selected_skills
        )

        total = (
            curriculum_amount
            + skills_amount
        )

        if (
            selected_subjects
            and selected_skills
        ):
            if plan == "full_term":
                subscription_type = "full_term"
            else:
                subscription_type = "mixed"

        elif selected_skills:
            subscription_type = "skills"

        elif plan == "full_term":
            subscription_type = "full_term"

        else:
            subscription_type = "subjects"

        SubscriptionRequest.objects.create(
            student=student_obj,
            request_type="addition",
            amount=total,
            curriculum_amount=curriculum_amount,
            skills_amount=skills_amount,
            subscription_type=subscription_type,
            selected_subjects=selected_subjects,
            selected_skills=[
                skill.name
                for skill in selected_skills
            ],
            transfer_image=transfer_image,
            status="pending",
        )

        common_context["success"] = True
        common_context["amount"] = total
        common_context["selected_subjects"] = (
            selected_subjects
        )
        common_context["selected_skills"] = [
            skill.name
            for skill in selected_skills
        ]

        return render(
            request,
            "main/add_content.html",
            common_context,
        )

    return render(
        request,
        "main/add_content.html",
        common_context,
    )


# =========================================================
# Skill Detail
# =========================================================

@login_required
def skill_detail(request, skill_id):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    skill = get_object_or_404(
        Skill,
        pk=skill_id,
        is_active=True,
    )

    subscription_obj = (
        SkillSubscription.objects
        .filter(
            student=student_obj,
            skill=skill,
            is_active=True,
        )
        .first()
    )

    if not subscription_obj:
        raise Http404(
            "المهارة غير مفعلة لهذا الطالب."
        )

    lessons = (
        SkillLesson.objects
        .filter(
            skill=skill,
            is_active=True,
        )
        .order_by(
            "order",
            "id",
        )
    )

    skill_homeworks = (
        SkillHomework.objects
        .filter(
            skill=skill,
            is_active=True,
        )
        .prefetch_related("questions")
        .order_by("created_at", "id")
    )

    skill_homework_submissions = {
        submission.homework_id: submission
        for submission in (
            SkillHomeworkSubmission.objects
            .filter(
                student=student_obj,
                homework__skill=skill,
            )
        )
    }

    skill_homework_results = (
        SkillHomeworkResult.objects
        .filter(
            student=student_obj,
            homework__skill=skill,
        )
        .select_related("homework")
        .order_by("-created_at")
    )

    lesson_progress = []

    for lesson in lessons:
        stat = (
            LessonWatchStat.objects
            .filter(
                student=student_obj,
                lesson_id=lesson.id,
            )
            .first()
        )

        is_watched = bool(
            stat
            and (
                stat.view_count > 0
                or stat.watch_seconds > 0
            )
        )

        related_homeworks = []

        for homework in skill_homeworks:
            if getattr(
                homework,
                "lesson_id",
                None,
            ) == lesson.id:

                submission = (
                    skill_homework_submissions.get(
                        homework.id
                    )
                )

                result = (
                    skill_homework_results
                    .filter(
                        homework=homework
                    )
                    .first()
                )

                related_homeworks.append(
                    {
                        "homework": homework,
                        "submission": submission,
                        "result": result,
                        "submitted": bool(
                            submission
                            and submission.status
                            in [
                                "submitted",
                                "graded",
                            ]
                        ),
                    }
                )

        lesson_progress.append(
            {
                "lesson": lesson,
                "watch_stat": stat,
                "is_watched": is_watched,
                "homeworks": related_homeworks,
            }
        )

    settings_obj = get_platform_settings()

    return render(
        request,
        "main/skill_detail.html",
        {
            "student": student_obj,
            "skill": skill,
            "subscription": subscription_obj,
            "lessons": lessons,
            "skill_homeworks": skill_homeworks,
            "homeworks": skill_homeworks,

            "skill_homework_submissions": (
                skill_homework_submissions
            ),
            "submissions": skill_homework_submissions,

            "skill_homework_results": (
                skill_homework_results
            ),
            "homework_results": skill_homework_results,

            "lesson_progress": lesson_progress,

            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# تسليم واجب المهارات
# =========================================================

@login_required
def skill_homework_detail(request, homework_id):
    student_obj = get_current_student(request)

    if not student_obj or not student_obj.is_active:
        return redirect("old_student")

    homework = get_object_or_404(
        SkillHomework.objects
        .select_related("skill")
        .prefetch_related("questions"),
        pk=homework_id,
        is_active=True,
    )

    subscription_obj = (
        SkillSubscription.objects
        .filter(
            student=student_obj,
            skill=homework.skill,
            is_active=True,
        )
        .first()
    )

    if not subscription_obj:
        raise Http404(
            "هذا الواجب غير متاح لك."
        )

    submission = (
        SkillHomeworkSubmission.objects
        .filter(
            student=student_obj,
            homework=homework,
        )
        .first()
    )

    result = (
        SkillHomeworkResult.objects
        .filter(
            student=student_obj,
            homework=homework,
        )
        .first()
    )

    if homework.homework_type == "paper":
        if request.method == "POST":
            uploaded_file = request.FILES.get(
                "uploaded_file"
            )

            if not uploaded_file:
                messages.error(
                    request,
                    "من فضلك اختاري ملف الإجابة أولًا.",
                )

            else:
                if submission:
                    submission.uploaded_file = (
                        uploaded_file
                    )

                    submission.status = "submitted"
                    submission.submitted_at = timezone.now()
                    submission.graded_at = None
                    submission.save()

                else:
                    submission = (
                        SkillHomeworkSubmission.objects.create(
                            student=student_obj,
                            homework=homework,
                            uploaded_file=uploaded_file,
                            status="submitted",
                            submitted_at=timezone.now(),
                        )
                    )

                messages.success(
                    request,
                    "تم تسليم الواجب الورقي بنجاح ✅",
                )

                return redirect(
                    "skill_detail",
                    skill_id=homework.skill_id,
                )

        return render(
            request,
            "main/skill_homework_detail.html",
            {
                "student": student_obj,
                "skill": homework.skill,
                "homework": homework,
                "questions": [],
                "submission": submission,
                "result": result,
                "is_paper": True,
                "is_electronic": False,
            },
        )

    questions = (
        homework.questions.all()
        .order_by(
            "order",
            "id",
        )
    )

    if (
        request.method == "GET"
        and submission
        and submission.status == "graded"
        and result
    ):
        percentage = 0

        if result.max_score:
            percentage = round(
                (
                    result.score
                    / result.max_score
                ) * 100,
                1,
            )

        return render(
            request,
            "main/skill_homework_detail.html",
            {
                "student": student_obj,
                "skill": homework.skill,
                "homework": homework,
                "questions": questions,
                "submission": submission,
                "result": result,
                "percentage": percentage,
                "already_submitted": True,
                "is_paper": False,
                "is_electronic": True,
            },
        )

    if request.method == "POST":
        if submission:
            submission.answers.all().delete()

        else:
            submission = (
                SkillHomeworkSubmission.objects.create(
                    student=student_obj,
                    homework=homework,
                    status="submitted",
                    submitted_at=timezone.now(),
                )
            )

        score = 0
        max_score = 0
        correct_count = 0

        for question in questions:
            selected_answer = (
                request.POST.get(
                    f"question_{question.id}",
                    "",
                )
                or ""
            ).strip()

            is_correct = (
                selected_answer
                == question.correct_answer
            )

            mark_obtained = (
                question.mark
                if is_correct
                else 0
            )

            score += mark_obtained
            max_score += question.mark

            if is_correct:
                correct_count += 1

            SkillHomeworkAnswer.objects.create(
                submission=submission,
                question=question,
                selected_answer=selected_answer,
                is_correct=is_correct,
                mark_obtained=mark_obtained,
            )

        submission.status = "graded"

        submission.submitted_at = (
            submission.submitted_at
            or timezone.now()
        )

        submission.graded_at = timezone.now()

        submission.save()

        result, _ = (
            SkillHomeworkResult.objects
            .get_or_create(
                student=student_obj,
                homework=homework,
            )
        )

        result.score = score
        result.max_score = max_score
        result.feedback = (
            "تم تصحيح الواجب الإلكتروني تلقائيًا."
        )

        result.save()

        percentage = 0

        if max_score > 0:
            percentage = round(
                (
                    score
                    / max_score
                ) * 100,
                1,
            )

        return render(
            request,
            "main/skill_homework_result.html",
            {
                "student": student_obj,
                "skill": homework.skill,
                "homework": homework,
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "correct": correct_count,
                "total": questions.count(),
                "result": result,
            },
        )

    return render(
        request,
        "main/skill_homework_detail.html",
        {
            "student": student_obj,
            "skill": homework.skill,
            "homework": homework,
            "questions": questions,
            "submission": submission,
            "result": result,
            "already_submitted": False,
            "is_paper": False,
            "is_electronic": True,
        },
    )


# =========================================================
# ولي الأمر
# =========================================================

def parent(request):
    """
    ولي الأمر يدخل رقم الهاتف فقط.

    النظام يبحث عن كل الطلاب الذين يحملون
    نفس رقم ولي الأمر الموجود في Student.parent_phone.
    """

    error = None
    students = Student.objects.none()
    parent_phone = ""

    def normalize_phone(phone):
        phone = str(phone or "").strip()

        arabic_digits = "٠١٢٣٤٥٦٧٨٩"
        english_digits = "0123456789"

        translation_table = str.maketrans(
            arabic_digits,
            english_digits,
        )

        phone = phone.translate(
            translation_table
        )

        phone = (
            phone.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if phone.startswith("+20"):
            phone = "0" + phone[3:]

        elif phone.startswith("20") and len(phone) == 12:
            phone = "0" + phone[2:]

        return phone

    if request.method == "POST":

        parent_phone = (
            request.POST.get(
                "parent_phone",
                "",
            )
            or ""
        ).strip()

        normalized_phone = normalize_phone(
            parent_phone
        )

        if not normalized_phone:

            error = (
                "من فضلك اكتبي رقم ولي الأمر."
            )

        else:

            all_students = (
                Student.objects
                .exclude(
                    parent_phone=""
                )
                .order_by(
                    "student_name"
                )
            )

            matching_students = []

            for student_obj in all_students:

                saved_phone = normalize_phone(
                    student_obj.parent_phone
                )

                if saved_phone == normalized_phone:
                    matching_students.append(
                        student_obj
                    )

            if matching_students:

                students = matching_students

                request.session[
                    "parent_phone"
                ] = normalized_phone

            else:

                error = (
                    "رقم ولي الأمر غير مسجل على المنصة."
                )

    settings_obj = get_platform_settings()

    return render(
        request,
        "main/parent.html",
        {
            "students": students,
            "parent_phone": parent_phone,
            "error": error,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# صفحة الطالب لولي الأمر
# =========================================================

def parent_student(request, student_id):
    parent_phone = (
        request.session.get(
            "parent_phone",
            "",
        )
        or ""
    ).strip()

    if not parent_phone:
        return redirect("parent")

    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"

    translation_table = str.maketrans(
        arabic_digits,
        english_digits,
    )

    parent_phone = parent_phone.translate(
        translation_table
    )

    parent_phone = (
        parent_phone
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if parent_phone.startswith("+20"):
        parent_phone = "0" + parent_phone[3:]

    elif (
        parent_phone.startswith("20")
        and len(parent_phone) == 12
    ):
        parent_phone = "0" + parent_phone[2:]

    student_obj = get_object_or_404(
        Student,
        id=student_id,
    )

    student_phone = (
        str(
            student_obj.parent_phone
            or ""
        )
        .strip()
        .translate(translation_table)
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if student_phone.startswith("+20"):
        student_phone = "0" + student_phone[3:]

    elif (
        student_phone.startswith("20")
        and len(student_phone) == 12
    ):
        student_phone = "0" + student_phone[2:]

    if student_phone != parent_phone:
        return redirect("parent")

    return render(
        request,
        "main/parent_student.html",
        {
            "student": student_obj,
        },
    )


# =========================================================
# منهج الطالب - لولي الأمر
# =========================================================

def parent_curriculum(request, student_id):
    parent_phone = (
        request.session.get(
            "parent_phone",
            "",
        )
        or ""
    ).strip()

    if not parent_phone:
        return redirect("parent")

    student_obj = get_object_or_404(
        Student,
        id=student_id,
        parent_phone=parent_phone,
    )

    progress = get_subject_progress_data(
        student_obj
    )

    settings_obj = get_platform_settings()

    return render(
        request,
        "main/parent_curriculum.html",
        {
            "student": student_obj,
            "progress": progress,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# مهارات الطالب - لولي الأمر
# =========================================================

def parent_skills(request, student_id):
    parent_phone = (
        request.session.get(
            "parent_phone",
            "",
        )
        or ""
    ).strip()

    if not parent_phone:
        return redirect("parent")

    student_obj = get_object_or_404(
        Student,
        id=student_id,
        parent_phone=parent_phone,
    )

    progress = get_skill_progress_data(
        student_obj
    )

    settings_obj = get_platform_settings()

    return render(
        request,
        "main/parent_skills.html",
        {
            "student": student_obj,
            "progress": progress,
            "support_whatsapp": build_whatsapp_link(
                settings_obj.whatsapp_number
            ),
        },
    )


# =========================================================
# AI Chat
# =========================================================

@login_required
def ai_chat(request):
    """
    مساعد المنصة بالذكاء الاصطناعي.

    المساعد هنا خاص بمشاكل واستخدام المنصة:
    - التسجيل
    - تسجيل الدخول
    - نسيان كلمة المرور
    - الاشتراكات
    - ظهور المواد والمهارات
    - مشاكل الحصص والفيديوهات والواجبات
    - شرح طريقة استخدام المنصة

    أما الأسئلة الخاصة بشرح محتوى الحصة نفسها
    فتظل من خلال "اسأل مدرس".
    """

    student = get_current_student(request)

    if not student:
        messages.error(
            request,
            "لازم تسجلي دخولك الأول."
        )
        return redirect("old_student")

    conversation, _ = AIConversation.objects.get_or_create(
        student=student,
        context_type="platform",
        status="open",
        defaults={
            "title": "مساعد المنصة",
        },
    )

    if request.method == "POST":
        message_text = (
            request.POST.get("message")
            or ""
        ).strip()

        image = request.FILES.get("image")

        if not message_text and not image:
            messages.error(
                request,
                "اكتبي سؤالك أو ابعتي صورة للمشكلة."
            )
            return redirect("ai_chat")

        image_data_url = None

        if image:
            if image.size > MAX_AI_IMAGE_SIZE:
                messages.error(
                    request,
                    "حجم الصورة كبير جدًا. الحد الأقصى 10 ميجابايت."
                )
                return redirect("ai_chat")

            if image.content_type not in ALLOWED_AI_IMAGE_TYPES:
                messages.error(
                    request,
                    "نوع الصورة غير مسموح. استخدمي JPG أو PNG أو WEBP."
                )
                return redirect("ai_chat")

            image_bytes = image.read()
            encoded_image = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            image_data_url = (
                f"data:{image.content_type};base64,{encoded_image}"
            )

        AIMessage.objects.create(
            conversation=conversation,
            sender_type="student",
            message=message_text,
            image=image if image else None,
        )

        system_instructions = """
أنتِ "مساعد المنصة" الذكي لمنصة تعليمية عربية.

مهمتك الأساسية هي مساعدة الطالب في استخدام المنصة وحل مشاكلها، وليس شرح
محتوى الدروس بدل المدرس.

يمكنك المساعدة في:
1. إنشاء حساب طالب جديد.
2. تسجيل الدخول.
3. مشاكل رقم الهاتف.
4. مشاكل كلمة المرور.
5. نسيان كلمة المرور وشرح خطوات الاسترداد الآمنة.
6. الاشتراك في المواد.
7. الاشتراك في المهارات.
8. فهم أسعار الاشتراكات وطريقة إرسال إثبات الدفع.
9. ظهور أو عدم ظهور المواد المشتركة.
10. الوصول إلى المنهج.
11. الوصول إلى المهارات.
12. فتح الحصص والفيديوهات.
13. الواجبات والامتحانات والنتائج.
14. شرح طريقة التنقل داخل المنصة.
15. مساعدة الطالب إذا أرسل صورة لشاشة بها مشكلة.

قواعد مهمة جدًا:

- تحدثي بالعربية وبأسلوب بسيط وودود.
- استخدمي اللهجة المصرية الخفيفة عندما يكون ذلك مناسبًا.
- كوني واضحة وخطوة بخطوة.
- إذا كانت المشكلة تخص شرح درس أو حل سؤال من محتوى حصة معينة،
  وجهي الطالب إلى زر "اسأل مدرس".
- لا تدّعي أنكِ تستطيعين تنفيذ عملية غير متاحة لكِ.
- لا تطلبي من الطالب إرسال كلمة المرور الحالية.
- لا تطلبي من الطالب إرسال أي كلمة مرور في المحادثة.
- لا تكشفي بيانات طالب آخر.
- لا تكشفي معلومات إدارية أو سرية.
- لا تغيري كلمة مرور الطالب اعتمادًا على رقم الهاتف فقط.
- إذا نسي الطالب كلمة المرور، اشرحي له أن تغييرها يحتاج إلى خطوة
  تحقق آمنة قبل تنفيذ التغيير.
- إذا كان السؤال غير متعلق بالمنصة، أخبري الطالب بلطف أن المساعد
  مخصص لمساعدة استخدام المنصة.
- إذا أرسل الطالب صورة، افحصي محتواها وحاولي تحديد المشكلة الظاهرة
  بدون اختلاق معلومات غير موجودة في الصورة.

أنتِ مساعد للمنصة، ولستِ المدرس المسؤول عن شرح المنهج.
"""

        previous_messages = (
            conversation.messages
            .order_by("created_at")
        )

        api_messages = []

        for old_message in previous_messages:
            role = (
                "user"
                if old_message.sender_type == "student"
                else "assistant"
            )

            content = []

            if old_message.message:
                content.append(
                    {
                        "type": "input_text",
                        "text": old_message.message,
                    }
                )

            if old_message.image:
                try:
                    with old_message.image.open(
                        "rb"
                    ) as image_file:
                        old_image_bytes = (
                            image_file.read()
                        )

                    old_encoded = base64.b64encode(
                        old_image_bytes
                    ).decode("utf-8")

                    content.append(
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:image/jpeg;base64,{old_encoded}"
                            ),
                        }
                    )
                except Exception:
                    pass

            if content:
                api_messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        current_content = []

        if message_text:
            current_content.append(
                {
                    "type": "input_text",
                    "text": message_text,
                }
            )

        if image_data_url:
            current_content.append(
                {
                    "type": "input_image",
                    "image_url": image_data_url,
                }
            )

        api_messages.append(
            {
                "role": "user",
                "content": current_content,
            }
        )

        try:
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY
            )

            response = client.responses.create(
                model="gpt-5.6-luna",
                instructions=system_instructions,
                input=api_messages,
            )

            ai_text = (
                getattr(
                    response,
                    "output_text",
                    None,
                )
                or "معلش، مقدرتش أطلع رد دلوقتي. جربي تاني."
            )

        except Exception:
            ai_text = (
                "معلش، حصلت مشكلة مؤقتة في المساعد الذكي. "
                "جربي تاني بعد شوية."
            )

        AIMessage.objects.create(
            conversation=conversation,
            sender_type="ai",
            message=ai_text,
        )

        conversation.title = "مساعد المنصة"

        conversation.save(
            update_fields=[
                "title",
                "updated_at",
            ]
        )

        return redirect("ai_chat")

    return render(
        request,
        "main/ai_chat.html",
        {
            "conversation": conversation,
            "student": student,
        },
    )


# =========================================================
# Prices
# =========================================================

def prices(request):
    ensure_grade_settings()

    settings_obj = get_platform_settings()

    grades = (
        GradeSetting.objects
        .filter(is_active=True)
        .order_by("id")
    )

    available_subjects = (
        AvailableSubject.objects
        .filter(
            is_active=True,
            grade__is_active=True,
        )
        .select_related("grade")
        .order_by(
            "grade__id",
            "school_type",
            "subject_name",
        )
    )

    grade_data = []

    for grade in grades:
        grade_subjects = (
            available_subjects
            .filter(grade=grade)
        )

        arabic_subjects = (
            grade_subjects
            .filter(school_type="عربي")
        )

        language_subjects = (
            grade_subjects
            .filter(school_type="لغات")
        )

        grade_data.append(
            {
                "grade": grade,
                "arabic_subjects": arabic_subjects,
                "language_subjects": language_subjects,
            }
        )

    skills = (
        Skill.objects
        .filter(is_active=True)
        .order_by("name")
    )

    return render(
        request,
        "main/prices.html",
        {
            "grade_data": grade_data,
            "skills": skills,
            "settings": settings_obj,
        },
    )


# =========================================================
# Platform AI
# =========================================================

def platform_ai(request):
    """
    مساعد المنصة العام.

    يعمل من الصفحة الرئيسية حتى لو الطالب غير مسجل دخول.
    المحادثة هنا مؤقتة داخل Session للزائر.
    """

    if request.method == "POST":
        message_text = (
            request.POST.get("message")
            or ""
        ).strip()

        if not message_text:
            messages.error(
                request,
                "اكتبي سؤالك الأول."
            )
            return redirect("platform_ai")

        try:
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY
            )

            system_instructions = """
أنتِ "مساعد المنصة" الذكي.

مهمتك مساعدة الزائر أو الطالب في فهم واستخدام المنصة التعليمية.

يمكنك المساعدة في:
- إنشاء حساب جديد.
- تسجيل الدخول.
- مشاكل التسجيل.
- مشاكل رقم الهاتف.
- نسيان كلمة المرور.
- الاشتراكات.
- الدفع وإرسال إثبات الدفع.
- ظهور المواد أو المهارات.
- الوصول للحصص والفيديوهات.
- الواجبات والامتحانات والنتائج.
- شرح طريقة استخدام المنصة.

قواعد مهمة:
- تحدثي بالعربية بأسلوب بسيط وودود.
- استخدمي اللهجة المصرية الخفيفة عند الحاجة.
- لا تطلبي من المستخدم إرسال كلمة المرور.
- لا تغيري كلمة المرور اعتمادًا على رقم الهاتف فقط.
- تغيير كلمة المرور يحتاج إلى تحقق آمن.
- إذا كان السؤال عن شرح محتوى درس معين، وجهي الطالب إلى "اسأل مدرس".
- لا تدّعي تنفيذ شيء لا تستطيعين تنفيذه.
"""

            response = client.responses.create(
                model="gpt-5.6-luna",
                instructions=system_instructions,
                input=message_text,
            )

            ai_text = (
                getattr(
                    response,
                    "output_text",
                    None,
                )
                or "معلش، مقدرتش أطلع رد دلوقتي."
            )

        except Exception:
            ai_text = (
                "معلش، حصلت مشكلة مؤقتة في المساعد. "
                "جربي تاني بعد شوية."
            )

        request.session[
            "platform_ai_question"
        ] = message_text

        request.session[
            "platform_ai_answer"
        ] = ai_text

        return redirect("platform_ai")

    return render(
        request,
        "main/platform_ai.html",
        {
            "question": request.session.get(
                "platform_ai_question",
                ""
            ),
            "answer": request.session.get(
                "platform_ai_answer",
                ""
            ),
        },
    )


# =========================================================
# استعادة كلمة المرور
# =========================================================

def password_reset_request(request):
    """
    استعادة كلمة المرور بشكل آمن:

    1. الطالب يدخل رقم الهاتف.
    2. لو الحساب لديه بريد إلكتروني مسجل:
       يتم إنشاء OTP وإرساله إلى البريد.
    3. الطالب يدخل OTP.
    4. بعد نجاح التحقق يسمح له بإدخال كلمة مرور جديدة.
    5. يتم تغيير كلمة المرور باستخدام set_password().
    """

    # -----------------------------------------------------
    # تحديد الخطوة الحالية
    # -----------------------------------------------------

    verified = bool(
        request.session.get(
            "password_reset_verified",
            False,
        )
    )

    student_id = request.session.get(
        "password_reset_student_id"
    )

    student = None

    if student_id:
        student = (
            Student.objects
            .filter(
                id=student_id
            )
            .select_related("user")
            .first()
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        action = (
            request.POST.get(
                "action",
                "send_code",
            )
            or "send_code"
        ).strip()

        # =================================================
        # الخطوة 1: إرسال كود OTP
        # =================================================

        if action == "send_code":

            student_phone = (
                request.POST.get(
                    "student_phone"
                )
                or ""
            ).strip()

            if not student_phone:
                messages.error(
                    request,
                    "اكتبي رقم الهاتف."
                )

                return redirect(
                    "password_reset_request"
                )

            student = (
                Student.objects
                .filter(
                    student_phone=student_phone
                )
                .select_related("user")
                .first()
            )

            # لا نكشف هل الرقم موجود أم لا
            if not student:
                messages.success(
                    request,
                    "لو الرقم مسجل على المنصة، هتوصلك خطوات استعادة كلمة المرور على البريد الإلكتروني المسجل."
                )

                return redirect(
                    "password_reset_request"
                )

            # لو لا يوجد بريد إلكتروني
            if not student.email:
                messages.success(
                    request,
                    "لو الرقم مسجل على المنصة، هتوصلك خطوات استعادة كلمة المرور على البريد الإلكتروني المسجل."
                )

                return redirect(
                    "password_reset_request"
                )

            # -------------------------------------------------
            # منع طلب أكواد متتالية بسرعة
            # -------------------------------------------------

            sent_at = request.session.get(
                "password_reset_sent_at"
            )

            if sent_at:

                try:
                    elapsed = (
                        timezone.now().timestamp()
                        - float(sent_at)
                    )

                    if (
                        elapsed
                        < PASSWORD_RESET_RESEND_SECONDS
                    ):
                        remaining_seconds = max(
                            1,
                            int(
                                PASSWORD_RESET_RESEND_SECONDS
                                - elapsed
                            )
                        )

                        messages.error(
                            request,
                            (
                                "استني شوية قبل طلب كود جديد. "
                                f"جربي بعد {remaining_seconds} ثانية."
                            ),
                        )

                        return redirect(
                            "password_reset_request"
                        )

                except (
                    ValueError,
                    TypeError,
                ):
                    pass

            # -------------------------------------------------
            # إنشاء OTP آمن
            # -------------------------------------------------

            code = str(
                secrets.randbelow(900000)
                + 100000
            )

            # إلغاء أي أكواد قديمة غير مستخدمة
            PasswordResetOTP.objects.filter(
                student=student,
                is_used=False,
            ).update(
                is_used=True
            )

            otp = PasswordResetOTP.objects.create(
                student=student,
                code=code,
                expires_at=(
                    timezone.now()
                    + timedelta(
                        minutes=PASSWORD_RESET_CODE_MINUTES
                    )
                ),
            )

            # حفظ الطالب في Session
            request.session[
                "password_reset_student_id"
            ] = student.id

            request.session[
                "password_reset_verified"
            ] = False

            request.session[
                "password_reset_sent_at"
            ] = timezone.now().timestamp()

            # -------------------------------------------------
            # إرسال البريد
            # -------------------------------------------------

            email_subject = (
                "كود استعادة كلمة المرور - منصة سما"
            )

            email_message = f"""
مرحبًا {student.student_name or "عزيزتي الطالبة"}،

تم طلب استعادة كلمة المرور لحسابك في منصة سما التعليمية.

كود التحقق الخاص بك هو:

{code}

الكود صالح لمدة {PASSWORD_RESET_CODE_MINUTES} دقائق فقط.

إذا لم تطلبي استعادة كلمة المرور، يمكنك تجاهل هذه الرسالة.

منصة سما التعليمية
"""

            try:

                send_mail(
                    email_subject,
                    email_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [student.email],
                    fail_silently=False,
                )

            except Exception as exc:

                print(
                    "Password reset email error:",
                    exc,
                )

                # إلغاء الكود إذا فشل إرسال البريد
                otp.is_used = True

                otp.save(
                    update_fields=[
                        "is_used"
                    ]
                )

                request.session.pop(
                    "password_reset_student_id",
                    None,
                )

                request.session.pop(
                    "password_reset_verified",
                    None,
                )

                request.session.pop(
                    "password_reset_sent_at",
                    None,
                )

                messages.error(
                    request,
                    (
                        "حصلت مشكلة أثناء إرسال كود التحقق. "
                        "جربي مرة تانية بعد شوية."
                    ),
                )

                return redirect(
                    "password_reset_request"
                )

            messages.success(
                request,
                (
                    "تم إرسال كود التحقق على البريد الإلكتروني "
                    f"{mask_email(student.email)}."
                ),
            )

            return redirect(
                "password_reset_request"
            )

        # =================================================
        # الخطوة 2: التحقق من OTP
        # =================================================

        elif action == "verify_code":

            student_id = request.session.get(
                "password_reset_student_id"
            )

            if not student_id:
                messages.error(
                    request,
                    "ابدئي استعادة كلمة المرور من جديد."
                )

                return redirect(
                    "password_reset_request"
                )

            student = (
                Student.objects
                .filter(
                    id=student_id
                )
                .select_related("user")
                .first()
            )

            if not student:
                clear_password_reset_session(
                    request
                )

                messages.error(
                    request,
                    "حدث خطأ. ابدئي الاستعادة من جديد."
                )

                return redirect(
                    "password_reset_request"
                )

            entered_code = (
                request.POST.get(
                    "code",
                    "",
                )
                or ""
            ).strip()

            if not entered_code:
                messages.error(
                    request,
                    "اكتبي كود التحقق."
                )

                return redirect(
                    "password_reset_request"
                )

            otp = (
                PasswordResetOTP.objects
                .filter(
                    student=student,
                    is_used=False,
                )
                .order_by("-created_at")
                .first()
            )

            if not otp:
                messages.error(
                    request,
                    "كود التحقق غير موجود. اطلبي كودًا جديدًا."
                )

                return redirect(
                    "password_reset_request"
                )

            # -------------------------------------------------
            # انتهاء الصلاحية
            # -------------------------------------------------

            if otp.is_expired:

                otp.is_used = True

                otp.save(
                    update_fields=[
                        "is_used"
                    ]
                )

                messages.error(
                    request,
                    "انتهت صلاحية الكود. اطلبي كودًا جديدًا."
                )

                return redirect(
                    "password_reset_request"
                )

            # -------------------------------------------------
            # عدد المحاولات
            # -------------------------------------------------

            if (
                otp.attempts
                >= PASSWORD_RESET_MAX_ATTEMPTS
            ):

                otp.is_used = True

                otp.save(
                    update_fields=[
                        "is_used"
                    ]
                )

                messages.error(
                    request,
                    "تم تجاوز عدد المحاولات المسموح بها. اطلبي كودًا جديدًا."
                )

                return redirect(
                    "password_reset_request"
                )

            # -------------------------------------------------
            # زيادة عدد المحاولات
            # -------------------------------------------------

            otp.attempts += 1

            otp.save(
                update_fields=[
                    "attempts"
                ]
            )

            # -------------------------------------------------
            # مقارنة الكود
            # -------------------------------------------------

            if entered_code != otp.code:

                remaining_attempts = max(
                    PASSWORD_RESET_MAX_ATTEMPTS
                    - otp.attempts,
                    0,
                )

                if remaining_attempts > 0:
                    messages.error(
                        request,
                        (
                            "كود التحقق غير صحيح. "
                            f"متبقي {remaining_attempts} محاولات."
                        ),
                    )

                else:
                    otp.is_used = True

                    otp.save(
                        update_fields=[
                            "is_used"
                        ]
                    )

                    messages.error(
                        request,
                        "تم تجاوز عدد المحاولات. اطلبي كودًا جديدًا."
                    )

                return redirect(
                    "password_reset_request"
                )

            # -------------------------------------------------
            # الكود صحيح
            # -------------------------------------------------

            otp.is_used = True

            otp.save(
                update_fields=[
                    "is_used"
                ]
            )

            request.session[
                "password_reset_verified"
            ] = True

            messages.success(
                request,
                "تم التحقق من الكود بنجاح ✅ دلوقتي اكتبي كلمة المرور الجديدة."
            )

            return redirect(
                "password_reset_request"
            )

        # =================================================
        # الخطوة 3: تغيير كلمة المرور
        # =================================================

        elif action == "set_password":

            student_id = request.session.get(
                "password_reset_student_id"
            )

            verified = bool(
                request.session.get(
                    "password_reset_verified",
                    False,
                )
            )

            if (
                not student_id
                or not verified
            ):
                clear_password_reset_session(
                    request
                )

                messages.error(
                    request,
                    "لازم تتحققي من كود الاستعادة الأول."
                )

                return redirect(
                    "password_reset_request"
                )

            student = (
                Student.objects
                .filter(
                    id=student_id
                )
                .select_related("user")
                .first()
            )

            if not student or not student.user:
                clear_password_reset_session(
                    request
                )

                messages.error(
                    request,
                    "حدث خطأ في الحساب. تواصلي مع الإدارة."
                )

                return redirect(
                    "password_reset_request"
                )

            new_password = (
                request.POST.get(
                    "new_password",
                    "",
                )
                or ""
            )

            confirm_password = (
                request.POST.get(
                    "confirm_password",
                    "",
                )
                or ""
            )

            if not new_password:
                messages.error(
                    request,
                    "اكتبي كلمة المرور الجديدة."
                )

                return redirect(
                    "password_reset_request"
                )

            if new_password != confirm_password:
                messages.error(
                    request,
                    "كلمتا المرور غير متطابقتين."
                )

                return redirect(
                    "password_reset_request"
                )

            if len(new_password) < 6:
                messages.error(
                    request,
                    "كلمة المرور يجب أن تكون 6 أحرف أو أرقام على الأقل."
                )

                return redirect(
                    "password_reset_request"
                )

            # -------------------------------------------------
            # تغيير كلمة المرور بشكل آمن
            # -------------------------------------------------

            student.user.set_password(
                new_password
            )

            student.user.save(
                update_fields=[
                    "password"
                ]
            )

            clear_password_reset_session(
                request
            )

            messages.success(
                request,
                "تم تغيير كلمة المرور بنجاح ✅ تقدري تسجلي دخولك دلوقتي."
            )

            return redirect(
                "old_student"
            )

        else:

            messages.error(
                request,
                "طلب غير صحيح."
            )

            return redirect(
                "password_reset_request"
            )

    # =====================================================
    # GET
    # =====================================================

    student_id = request.session.get(
        "password_reset_student_id"
    )

    verified = bool(
        request.session.get(
            "password_reset_verified",
            False,
        )
    )

    student = None

    if student_id:
        student = (
            Student.objects
            .filter(
                id=student_id
            )
            .select_related("user")
            .first()
        )

    if verified and not student:
        clear_password_reset_session(
            request
        )
        verified = False

    if verified:
        step = "password"

    elif student_id and student:
        step = "otp"

    else:
        step = "phone"

    return render(
        request,
        "main/password_reset_request.html",
        {
            "step": step,
            "student": student,
            "masked_email": (
                mask_email(student.email)
                if student
                else ""
            ),
            "password_reset_verified": verified,
        },
    )