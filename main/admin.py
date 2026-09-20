from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    AIConversation,
    AIMessage,
    AvailableSubject,
    ClassRoom,
    Exam,
    ExamResult,
    GradeSetting,
    Homework,
    HomeworkAnswer,
    HomeworkQuestion,
    HomeworkResult,
    HomeworkSubmission,
    Lesson,
    LessonWatchStat,
    PlatformSettings,
    Skill,
    SkillHomework,
    SkillHomeworkAnswer,
    SkillHomeworkQuestion,
    SkillHomeworkResult,
    SkillHomeworkSubmission,
    SkillLesson,
    SkillSubscription,
    Student,
    StudyMaterial,
    SubjectSubscription,
    SubscriptionRequest,
)


# =========================================================
# 1) تغيير باسورد الطالب
# =========================================================

class StudentPasswordForm(forms.Form):

    new_password = forms.CharField(
        label="كلمة المرور الجديدة",
        widget=forms.PasswordInput,
        min_length=4,
    )

    confirm_password = forms.CharField(
        label="تأكيد كلمة المرور",
        widget=forms.PasswordInput,
        min_length=4,
    )

    def clean(self):

        cleaned_data = super().clean()

        password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password:

            if password != confirm_password:

                raise forms.ValidationError(
                    "كلمتا المرور غير متطابقتين."
                )

        return cleaned_data


# =========================================================
# 2) إعدادات الصفوف
# =========================================================

@admin.register(GradeSetting)
class GradeSettingAdmin(admin.ModelAdmin):

    list_display = (
        "grade",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "grade",
    )

    ordering = (
        "grade",
    )


# =========================================================
# 3) المواد المتاحة
# =========================================================

@admin.register(AvailableSubject)
class AvailableSubjectAdmin(admin.ModelAdmin):

    list_display = (
        "subject_name",
        "grade",
        "school_type",
        "monthly_price",
        "full_term_price",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "grade",
        "school_type",
        "is_active",
    )

    search_fields = (
        "subject_name",
        "grade__grade",
    )

    ordering = (
        "grade",
        "school_type",
        "subject_name",
    )

    fieldsets = (
        (
            "بيانات المادة",
            {
                "fields": (
                    "grade",
                    "school_type",
                    "subject_name",
                    "is_active",
                )
            },
        ),
        (
            "أسعار المادة",
            {
                "fields": (
                    "monthly_price",
                    "full_term_price",
                ),
                "description": (
                    "حددي سعر كل مادة بشكل مستقل "
                    "عن باقي المواد."
                ),
            },
        ),
        (
            "التواريخ",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


# =========================================================
# 4) المهارات
# =========================================================

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "course_price",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "description",
    )

    filter_horizontal = (
        "prerequisites",
    )

    ordering = (
        "name",
    )


# =========================================================
# 5) دروس المهارات
# =========================================================

@admin.register(SkillLesson)
class SkillLessonAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "skill",
        "order",
        "is_active",
        "created_at",
    )

    list_filter = (
        "skill",
        "is_active",
    )

    search_fields = (
        "title",
        "description",
        "skill__name",
    )

    ordering = (
        "skill",
        "order",
        "id",
    )


# =========================================================
# 6) أسئلة واجبات المهارات
# =========================================================

class SkillHomeworkQuestionInline(
    admin.TabularInline
):

    model = SkillHomeworkQuestion

    extra = 1

    fields = (
        "question_text",
        "choice_a",
        "choice_b",
        "choice_c",
        "choice_d",
        "correct_answer",
        "mark",
        "order",
    )


# =========================================================
# 7) واجبات المهارات
# =========================================================

@admin.register(SkillHomework)
class SkillHomeworkAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "skill",
        "lesson",
        "homework_type",
        "total_marks",
        "is_active",
        "created_at",
    )

    list_filter = (
        "skill",
        "lesson",
        "homework_type",
        "is_active",
    )

    search_fields = (
        "title",
        "description",
        "skill__name",
        "lesson__title",
    )

    ordering = (
        "-created_at",
    )

    inlines = (
        SkillHomeworkQuestionInline,
    )

    fieldsets = (
        (
            "بيانات الواجب",
            {
                "fields": (
                    "skill",
                    "lesson",
                    "title",
                    "homework_type",
                    "description",
                    "file",
                    "total_marks",
                    "is_active",
                )
            },
        ),
    )


# =========================================================
# 8) أسئلة واجبات المهارات
# =========================================================

@admin.register(SkillHomeworkQuestion)
class SkillHomeworkQuestionAdmin(admin.ModelAdmin):

    list_display = (
        "question_text",
        "homework",
        "correct_answer",
        "mark",
        "order",
        "created_at",
    )

    list_filter = (
        "homework",
        "correct_answer",
    )

    search_fields = (
        "question_text",
        "homework__title",
    )

    ordering = (
        "homework",
        "order",
        "id",
    )


# =========================================================
# 9) اشتراكات المهارات
# =========================================================

@admin.register(SkillSubscription)
class SkillSubscriptionAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "skill",
        "is_active",
        "start_date",
        "created_at",
    )

    list_filter = (
        "skill",
        "is_active",
        "start_date",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "student__parent_phone",
        "skill__name",
    )

    ordering = (
        "-start_date",
    )


# =========================================================
# 10) تسليم واجبات المهارات
# =========================================================

@admin.register(SkillHomeworkSubmission)
class SkillHomeworkSubmissionAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "homework",
        "status",
        "submitted_at",
        "graded_at",
    )

    list_filter = (
        "status",
        "homework",
        "submitted_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "homework__title",
    )

    readonly_fields = (
        "submitted_at",
        "graded_at",
    )

    ordering = (
        "-submitted_at",
    )


# =========================================================
# 11) إجابات واجبات المهارات
# =========================================================

@admin.register(SkillHomeworkAnswer)
class SkillHomeworkAnswerAdmin(admin.ModelAdmin):

    list_display = (
        "submission",
        "question",
        "selected_answer",
        "is_correct",
        "mark_obtained",
    )

    list_filter = (
        "is_correct",
        "selected_answer",
    )

    search_fields = (
        "submission__student__student_name",
        "submission__student__student_phone",
        "question__question_text",
    )


# =========================================================
# 12) نتائج واجبات المهارات
# =========================================================

@admin.register(SkillHomeworkResult)
class SkillHomeworkResultAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "homework",
        "score",
        "max_score",
        "percentage_display",
        "created_at",
    )

    list_filter = (
        "homework",
        "created_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "homework__title",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(description="النسبة")
    def percentage_display(self, obj):

        if not obj.max_score:
            return "0%"

        percentage = (
            obj.score / obj.max_score
        ) * 100

        return f"{percentage:.1f}%"


# =========================================================
# 13) إعدادات المنصة
# =========================================================

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "whatsapp_number",
        "vodafone_cash_number",
        "curriculum_enabled",
        "curriculum_available_in_vacation",
        "skills_available_in_vacation",
    )

    list_filter = (
        "curriculum_enabled",
        "curriculum_available_in_vacation",
        "skills_available_in_vacation",
    )

    fieldsets = (
        (
            "بيانات الإعدادات",
            {
                "fields": (
                    "name",
                )
            },
        ),
        (
            "بيانات التواصل والدفع",
            {
                "fields": (
                    "whatsapp_number",
                    "vodafone_cash_number",
                )
            },
        ),
        (
            "إعدادات المنهج",
            {
                "fields": (
                    "curriculum_enabled",
                    "curriculum_available_in_vacation",
                )
            },
        ),
        (
            "إعدادات المهارات",
            {
                "fields": (
                    "skills_available_in_vacation",
                )
            },
        ),
        (
            "الإجازة",
            {
                "fields": (
                    "vacation_start_month",
                    "vacation_end_month",
                )
            },
        ),
        (
            "آخر تحديث",
            {
                "fields": (
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "updated_at",
    )


# =========================================================
# 14) الطلاب
# =========================================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):

    list_display = (
        "student_name",
        "student_phone",
        "parent_phone",
        "grade",
        "school_type",
        "is_active",
        "created_at",
        "change_password_button",
    )

    list_filter = (
        "grade",
        "school_type",
        "is_active",
        "created_at",
    )

    search_fields = (
        "student_name",
        "student_phone",
        "parent_phone",
    )

    ordering = (
        "-created_at",
    )

    # =====================================================
    # حذف الطالب مع حساب User المرتبط به
    # =====================================================

    def delete_model(self, request, obj):

        user = obj.user

        with transaction.atomic():

            obj.delete()

            if user:

                user.delete()

    def delete_queryset(self, request, queryset):

        user_ids = list(
            queryset
            .exclude(user__isnull=True)
            .values_list(
                "user_id",
                flat=True,
            )
        )

        with transaction.atomic():

            queryset.delete()

            User.objects.filter(
                pk__in=user_ids
            ).delete()

    @admin.display(description="تغيير الباسورد")
    def change_password_button(self, obj):

        url = reverse(
            "admin:student_change_password",
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">تغيير الباسورد</a>',
            url,
        )

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [
            path(
                "<int:student_id>/change-password/",
                self.admin_site.admin_view(
                    self.change_student_password
                ),
                name="student_change_password",
            ),
        ]

        return custom_urls + urls

    def change_student_password(
        self,
        request,
        student_id,
    ):

        student = get_object_or_404(
            Student,
            pk=student_id,
        )

        user = student.user

        if request.method == "POST":

            form = StudentPasswordForm(
                request.POST
            )

            if form.is_valid():

                if user is None:

                    messages.error(
                        request,
                        "هذا الطالب لا يوجد له حساب مستخدم.",
                    )

                else:

                    user.set_password(
                        form.cleaned_data[
                            "new_password"
                        ]
                    )

                    user.save()

                    self.message_user(
                        request,
                        "تم تغيير كلمة مرور الطالب بنجاح.",
                        level=messages.SUCCESS,
                    )

                    return redirect(
                        "admin:main_student_change",
                        student.pk,
                    )

        else:

            form = StudentPasswordForm()

        context = dict(
            self.admin_site.each_context(
                request
            ),
            title="تغيير كلمة مرور الطالب",
            student=student,
            form=form,
        )

        return render(
            request,
            "admin/change_student_password.html",
            context,
        )


# =========================================================
# 15) الفصول
# =========================================================

@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):

    list_display = (
        "name",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "name",
    )


# =========================================================
# 16) طلبات الاشتراك
# =========================================================

@admin.register(SubscriptionRequest)
class SubscriptionRequestAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "request_type",
        "subscription_type",
        "amount",
        "status",
        "created_at",
        "processed_at",
    )

    list_filter = (
        "request_type",
        "subscription_type",
        "status",
        "created_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "student__parent_phone",
    )

    readonly_fields = (
        "created_at",
        "processed_at",
    )

    fieldsets = (
        (
            "بيانات الطلب",
            {
                "fields": (
                    "student",
                    "request_type",
                    "subscription_type",
                    "amount",
                    "curriculum_amount",
                    "skills_amount",
                    "selected_subjects",
                    "selected_skills",
                    "status",
                    "transfer_image",
                )
            },
        ),
        (
            "سبب الرفض",
            {
                "fields": (
                    "rejection_reason",
                )
            },
        ),
        (
            "التواريخ",
            {
                "fields": (
                    "created_at",
                    "processed_at",
                )
            },
        ),
    )

    ordering = (
        "-created_at",
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):

        if obj.status == "rejected":

            reason = (
                obj.rejection_reason or ""
            ).strip()

            if not reason:

                messages.error(
                    request,
                    "يجب كتابة سبب رفض الطلب.",
                )

                return

        super().save_model(
            request,
            obj,
            form,
            change,
        )


# =========================================================
# 17) اشتراكات المواد
# =========================================================

@admin.register(SubjectSubscription)
class SubjectSubscriptionAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "subject",
        "plan_type",
        "start_date",
        "end_date",
        "is_active",
        "remaining_display",
    )

    list_filter = (
        "plan_type",
        "is_active",
        "subject",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "student__parent_phone",
        "subject",
    )

    ordering = (
        "-start_date",
    )

    @admin.display(
        description="المتبقي"
    )
    def remaining_display(
        self,
        obj,
    ):

        return obj.remaining_label


# =========================================================
# 18) ملفات المواد
# =========================================================

@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "grade",
        "material_type",
        "is_active",
        "created_at",
    )

    list_filter = (
        "grade",
        "material_type",
        "is_active",
    )

    search_fields = (
        "title",
        "grade",
        "description",
    )

    ordering = (
        "-created_at",
    )


# =========================================================
# 19) الدروس
# =========================================================

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "subject",
        "grade",
        "school_type",
        "is_active",
        "created_at",
    )

    list_filter = (
        "subject",
        "grade",
        "school_type",
        "is_active",
    )

    search_fields = (
        "title",
        "subject",
        "grade",
    )

    ordering = (
        "subject",
        "created_at",
        "id",
    )


# =========================================================
# 20) أسئلة واجبات المواد
# =========================================================

class HomeworkQuestionInline(
    admin.TabularInline
):

    model = HomeworkQuestion

    extra = 1

    fields = (
        "question_text",
        "choice_a",
        "choice_b",
        "choice_c",
        "choice_d",
        "correct_answer",
        "mark",
        "order",
    )


# =========================================================
# 21) واجبات المواد
# =========================================================

@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "subject",
        "grade",
        "school_type",
        "homework_type",
        "total_marks",
        "is_active",
        "created_at",
    )

    list_filter = (
        "subject",
        "grade",
        "school_type",
        "homework_type",
        "is_active",
    )

    search_fields = (
        "title",
        "description",
        "subject",
        "grade",
    )

    ordering = (
        "-created_at",
    )

    inlines = (
        HomeworkQuestionInline,
    )


# =========================================================
# 22) أسئلة واجبات المواد
# =========================================================

@admin.register(HomeworkQuestion)
class HomeworkQuestionAdmin(admin.ModelAdmin):

    list_display = (
        "question_text",
        "homework",
        "correct_answer",
        "mark",
        "order",
        "created_at",
    )

    list_filter = (
        "homework",
        "correct_answer",
    )

    search_fields = (
        "question_text",
        "homework__title",
    )

    ordering = (
        "homework",
        "order",
        "id",
    )


# =========================================================
# 23) تسليم واجبات المواد
# =========================================================

@admin.register(HomeworkSubmission)
class HomeworkSubmissionAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "homework",
        "status",
        "submitted_at",
        "graded_at",
    )

    list_filter = (
        "status",
        "homework",
        "submitted_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "homework__title",
    )

    readonly_fields = (
        "submitted_at",
        "graded_at",
    )

    ordering = (
        "-submitted_at",
    )


# =========================================================
# 24) إجابات واجبات المواد
# =========================================================

@admin.register(HomeworkAnswer)
class HomeworkAnswerAdmin(admin.ModelAdmin):

    list_display = (
        "submission",
        "question",
        "selected_answer",
        "is_correct",
        "mark_obtained",
    )

    list_filter = (
        "is_correct",
        "selected_answer",
    )

    search_fields = (
        "submission__student__student_name",
        "submission__student__student_phone",
        "question__question_text",
    )


# =========================================================
# 25) نتائج واجبات المواد
# =========================================================

@admin.register(HomeworkResult)
class HomeworkResultAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "homework",
        "score",
        "max_score",
        "percentage_display",
        "created_at",
    )

    list_filter = (
        "homework",
        "created_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "homework__title",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(description="النسبة")
    def percentage_display(
        self,
        obj,
    ):

        if not obj.max_score:
            return "0%"

        percentage = (
            obj.score / obj.max_score
        ) * 100

        return f"{percentage:.1f}%"


# =========================================================
# 26) الامتحانات
# =========================================================

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "subject",
        "grade",
        "school_type",
        "total_marks",
        "is_active",
        "created_at",
    )

    list_filter = (
        "subject",
        "grade",
        "school_type",
        "is_active",
    )

    search_fields = (
        "title",
        "description",
        "subject",
        "grade",
    )

    ordering = (
        "-created_at",
    )


# =========================================================
# 27) نتائج الامتحانات
# =========================================================

@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "exam",
        "score",
        "created_at",
    )

    list_filter = (
        "exam",
        "created_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "exam__title",
    )

    ordering = (
        "-created_at",
    )


# =========================================================
# 28) متابعة مشاهدة الدروس
# =========================================================

@admin.register(LessonWatchStat)
class LessonWatchStatAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "lesson",
        "view_count",
        "watch_seconds",
        "last_position",
        "updated_at",
    )

    list_filter = (
        "lesson",
        "updated_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "lesson__title",
    )

    ordering = (
        "-updated_at",
    )


# =========================================================
# 29) محادثات الذكاء الاصطناعي
# =========================================================

@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "title",
        "context_type",
        "subject",
        "skill",
        "status",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "context_type",
        "status",
        "subject",
        "skill",
        "created_at",
    )

    search_fields = (
        "student__student_name",
        "student__student_phone",
        "title",
        "subject",
    )

    ordering = (
        "-updated_at",
    )


# =========================================================
# 30) رسائل الذكاء الاصطناعي
# =========================================================

@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):

    list_display = (
        "conversation",
        "sender_type",
        "created_at",
    )

    list_filter = (
        "sender_type",
        "created_at",
    )

    search_fields = (
        "message",
        "conversation__student__student_name",
        "conversation__student__student_phone",
    )

    ordering = (
        "-created_at",
    )