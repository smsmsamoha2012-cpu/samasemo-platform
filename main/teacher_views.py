from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, redirect, render

from .models import TeacherQuestion, TeacherReply


# =========================================================
# تسجيل دخول المدرس
# =========================================================

def teacher_login(request):

    if request.user.is_authenticated and request.user.is_staff:
        return redirect("/teacher/dashboard/")

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None and user.is_staff:

            login(request, user)

            return redirect("/teacher/dashboard/")

        error = (
            "اسم المستخدم أو كلمة المرور غير صحيحة، "
            "أو الحساب غير مصرح له بالدخول."
        )

    return render(
        request,
        "main/teacher_login.html",
        {
            "error": error,
        },
    )


# =========================================================
# لوحة المدرس
# =========================================================

def teacher_dashboard(request):

    if (
        not request.user.is_authenticated
        or not request.user.is_staff
    ):
        return redirect("/teacher/")

    pending_questions_count = (
        TeacherQuestion.objects
        .filter(status="pending")
        .count()
    )

    return render(
        request,
        "main/teacher_dashboard.html",
        {
            "pending_questions_count": pending_questions_count,
        },
    )


# =========================================================
# أسئلة الطلاب للمدرس
# =========================================================

def teacher_questions(request):

    if (
        not request.user.is_authenticated
        or not request.user.is_staff
    ):
        return redirect("/teacher/")

    status_filter = (
        request.GET.get("status", "all") or "all"
    ).strip()

    questions = (
        TeacherQuestion.objects
        .select_related(
            "student",
            "lesson",
        )
        .prefetch_related("replies")
        .order_by("-created_at")
    )

    if status_filter in ["pending", "answered"]:

        questions = questions.filter(
            status=status_filter
        )

    else:

        status_filter = "all"

    pending_count = (
        TeacherQuestion.objects
        .filter(status="pending")
        .count()
    )

    answered_count = (
        TeacherQuestion.objects
        .filter(status="answered")
        .count()
    )

    return render(
        request,
        "main/teacher_questions.html",
        {
            "questions": questions,
            "status_filter": status_filter,
            "pending_count": pending_count,
            "answered_count": answered_count,
        },
    )


# =========================================================
# سؤال طالب + الرد عليه
# =========================================================

def teacher_question_detail(request, question_id):

    if (
        not request.user.is_authenticated
        or not request.user.is_staff
    ):
        return redirect("/teacher/")

    question = get_object_or_404(
        TeacherQuestion.objects
        .select_related(
            "student",
            "lesson",
        )
        .prefetch_related("replies"),
        pk=question_id,
    )

    if request.method == "POST":

        message_text = (
            request.POST.get("message", "") or ""
        ).strip()

        image = request.FILES.get("image")
        audio = request.FILES.get("audio")

        # =================================================
        # لازم يكون فيه محتوى للرد
        # =================================================

        if not message_text and not image and not audio:

            messages.error(
                request,
                "اكتبي الرد أو أرفقي صورة أو تسجيلًا صوتيًا.",
            )

            return redirect(
                "teacher_question_detail",
                question_id=question.id,
            )

        # =================================================
        # التحقق من الصورة
        # =================================================

        if image:

            content_type = (
                getattr(image, "content_type", "") or ""
            ).lower()

            allowed_image_types = {
                "image/jpeg",
                "image/png",
                "image/webp",
            }

            if content_type not in allowed_image_types:

                messages.error(
                    request,
                    "من فضلك اختاري صورة بصيغة JPG أو PNG أو WEBP.",
                )

                return redirect(
                    "teacher_question_detail",
                    question_id=question.id,
                )

            if image.size > 10 * 1024 * 1024:

                messages.error(
                    request,
                    "الصورة كبيرة جدًا. الحد الأقصى 10 ميجابايت.",
                )

                return redirect(
                    "teacher_question_detail",
                    question_id=question.id,
                )

        # =================================================
        # التحقق من التسجيل الصوتي
        # =================================================

        if audio:

            audio_content_type = (
                getattr(audio, "content_type", "") or ""
            ).lower()

            audio_name = (
                getattr(audio, "name", "") or ""
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
                    "teacher_question_detail",
                    question_id=question.id,
                )

            if audio.size > 20 * 1024 * 1024:

                messages.error(
                    request,
                    "التسجيل الصوتي كبير جدًا. الحد الأقصى 20 ميجابايت.",
                )

                return redirect(
                    "teacher_question_detail",
                    question_id=question.id,
                )

        # =================================================
        # إنشاء رد المدرس
        # =================================================

        TeacherReply.objects.create(
            question=question,
            message=message_text,
            image=image,
            audio=audio,
        )

        # =================================================
        # تحديث حالة السؤال
        # =================================================

        question.status = "answered"

        question.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        messages.success(
            request,
            "تم إرسال الرد للطالب بنجاح ✅",
        )

        return redirect(
            "teacher_question_detail",
            question_id=question.id,
        )

    replies = (
        question.replies
        .all()
        .order_by("created_at")
    )

    return render(
        request,
        "main/teacher_question_detail.html",
        {
            "question": question,
            "replies": replies,
        },
    )


# =========================================================
# تسجيل خروج المدرس
# =========================================================

def teacher_logout(request):

    logout(request)

    return redirect("/")
