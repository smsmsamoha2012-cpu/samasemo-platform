from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import include, path

from main.teacher_views import (
    teacher_dashboard,
    teacher_login,
    teacher_logout,
    teacher_questions,
    teacher_question_detail,
)

from main.views import (
    add_content,
    ai_chat,
    ask_teacher,
    curriculum_page,
    electronic_homework,
    home,
    lesson_watch_progress,
    old_student,
    old_student_subscription,
    parent,
    parent_curriculum,
    parent_skills,
    parent_student,
    password_reset_request,
    platform_ai,
    prices,
    protected_lesson_video,
    skill_detail,
    skill_homework_detail,
    skills_page,
    student,
    student_dashboard,
    student_logout,
    subject_lessons,
    subscription,
)


urlpatterns = [

    # =================================================
    # Admin
    # =================================================

    path(
        "admin/",
        admin.site.urls,
    ),


    # =================================================
    # الصفحة الرئيسية
    # =================================================

    path(
        "",
        home,
        name="home",
    ),


    # =================================================
    # robots.txt - السماح لمحركات البحث
    # =================================================

    path(
        "robots.txt",
        lambda request: HttpResponse(
            "User-agent: *\n"
            "Allow: /\n"
            "Sitemap: https://sama-platform.onrender.com/sitemap.xml\n",
            content_type="text/plain",
        ),
    ),


    # =================================================
    # طالب جديد
    # =================================================

    path(
        "student/",
        student,
        name="student",
    ),


    # =================================================
    # لوحة الطالب
    # =================================================

    path(
        "student/dashboard/",
        student_dashboard,
        name="student_dashboard",
    ),


    # =================================================
    # المنهج
    # =================================================

    path(
        "student/curriculum/",
        curriculum_page,
        name="curriculum_page",
    ),


    # =================================================
    # المهارات
    # =================================================

    path(
        "student/skills/",
        skills_page,
        name="skills_page",
    ),


    # =================================================
    # الاشتراك
    # =================================================

    path(
        "student/subscription/",
        subscription,
        name="subscription",
    ),


    # =================================================
    # إضافة مواد أو مهارات
    # =================================================

    path(
        "student/add-content/",
        add_content,
        name="add_content",
    ),


    # =================================================
    # صفحة المادة
    # =================================================

    path(
        "student/subject/<str:subject>/",
        subject_lessons,
        name="subject_lessons",
    ),


    # =================================================
    # اسأل مدرس - سؤال خاص بالدرس
    # =================================================

    path(
        "student/lesson/<int:lesson_id>/ask-teacher/",
        ask_teacher,
        name="ask_teacher",
    ),


    # =================================================
    # الواجب الإلكتروني للمواد
    # =================================================

    path(
        "student/homework/<int:homework_id>/",
        electronic_homework,
        name="electronic_homework",
    ),


    # =================================================
    # صفحة المهارة
    # =================================================

    path(
        "student/skill/<int:skill_id>/",
        skill_detail,
        name="skill_detail",
    ),


    # =================================================
    # واجب المهارة
    # =================================================

    path(
        "student/skill-homework/<int:homework_id>/",
        skill_homework_detail,
        name="skill_homework_detail",
    ),


    # =================================================
    # الفيديو المحمي
    # =================================================

    path(
        "student/video/<int:lesson_id>/",
        protected_lesson_video,
        name="protected_lesson_video",
    ),


    # =================================================
    # متابعة مشاهدة الفيديو
    # =================================================

    path(
        "student/video/<int:lesson_id>/progress/",
        lesson_watch_progress,
        name="lesson_watch_progress",
    ),


    # =================================================
    # الطالب القديم
    # =================================================

    path(
        "old-student/",
        old_student,
        name="old_student",
    ),


    # =================================================
    # طلب استعادة كلمة المرور
    # =================================================

    path(
        "student/password-reset-request/",
        password_reset_request,
        name="password_reset_request",
    ),


    # =================================================
    # اشتراك الطالب القديم
    # =================================================

    path(
        "old-student/subscription/",
        old_student_subscription,
        name="old_student_subscription",
    ),


    # =================================================
    # تسجيل الخروج
    # =================================================

    path(
        "student-logout/",
        student_logout,
        name="student_logout",
    ),


    # =================================================
    # الأسعار
    # =================================================

    path(
        "prices/",
        prices,
        name="prices",
    ),


    # =================================================
    # مساعد المنصة العام
    # =================================================

    path(
        "platform-ai/",
        platform_ai,
        name="platform_ai",
    ),


    # =================================================
    # الذكاء الاصطناعي الخاص بالطالب
    # =================================================

    path(
        "student/ai/",
        ai_chat,
        name="ai_chat",
    ),


    # =================================================
    # ولي الأمر
    # =================================================

    path(
        "parent/",
        parent,
        name="parent",
    ),


    # =================================================
    # صفحة طالب لولي الأمر
    # =================================================

    path(
        "parent/student/<int:student_id>/",
        parent_student,
        name="parent_student",
    ),


    # =================================================
    # منهج الطالب لولي الأمر
    # =================================================

    path(
        "parent/student/<int:student_id>/curriculum/",
        parent_curriculum,
        name="parent_curriculum",
    ),


    # =================================================
    # مهارات الطالب لولي الأمر
    # =================================================

    path(
        "parent/student/<int:student_id>/skills/",
        parent_skills,
        name="parent_skills",
    ),


    # =================================================
    # المعلم
    # =================================================

    path(
        "teacher/",
        teacher_login,
        name="teacher_login",
    ),

    path(
        "teacher/dashboard/",
        teacher_dashboard,
        name="teacher_dashboard",
    ),

    path(
        "teacher/questions/",
        teacher_questions,
        name="teacher_questions",
    ),

    path(
        "teacher/questions/<int:question_id>/",
        teacher_question_detail,
        name="teacher_question_detail",
    ),

    path(
        "teacher/logout/",
        teacher_logout,
        name="teacher_logout",
    ),


    # =================================================
    # Allauth
    # =================================================

    path(
        "accounts/",
        include("allauth.urls"),
    ),
]


# =====================================================
# Media أثناء التطوير
# =====================================================

if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )