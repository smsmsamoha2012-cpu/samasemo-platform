from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from main.teacher_views import (
    teacher_dashboard,
    teacher_login,
    teacher_logout,
)

from main.views import (
    add_content,
    ai_chat,
    curriculum_page,
    electronic_homework,
    home,
    lesson_watch_progress,
    old_student,
    old_student_subscription,
    prices,
    protected_lesson_video,
    skill_detail,
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
    # الواجب الإلكتروني
    # =================================================

    path(
        "student/homework/<int:homework_id>/",
        electronic_homework,
        name="electronic_homework",
    ),


    # =================================================
    # المهارة
    # =================================================

    path(
        "student/skill/<int:skill_id>/",
        skill_detail,
        name="skill_detail",
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
    # AI
    # =================================================

    path(
        "student/ai/",
        ai_chat,
        name="ai_chat",
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