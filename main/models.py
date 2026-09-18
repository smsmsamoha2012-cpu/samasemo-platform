from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# ====================================================
# الأسعار الافتراضية
# ====================================================

DEFAULT_MONTHLY_PRICES = {
    "الصف الأول الابتدائي": 50,
    "الصف الثاني الابتدائي": 50,
    "الصف الثالث الابتدائي": 50,

    "الصف الرابع الابتدائي": 100,
    "الصف الخامس الابتدائي": 100,
    "الصف السادس الابتدائي": 100,

    "الصف الأول الإعدادي": 150,
    "الصف الثاني الإعدادي": 150,

    "الصف الثالث الإعدادي": 250,
}


DEFAULT_FULL_TERM_PRICES = {
    "الصف الأول الابتدائي": 250,
    "الصف الثاني الابتدائي": 250,
    "الصف الثالث الابتدائي": 250,

    "الصف الرابع الابتدائي": 500,
    "الصف الخامس الابتدائي": 500,
    "الصف السادس الابتدائي": 500,

    "الصف الأول الإعدادي": 750,
    "الصف الثاني الإعدادي": 750,

    "الصف الثالث الإعدادي": 1000,
}


# ====================================================
# Student
# ====================================================

class Student(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="student_profile",
    )

    student_name = models.CharField(
        max_length=100,
        default="طالب",
        verbose_name="اسم الطالب",
    )

    grade = models.CharField(
        max_length=100,
        default="غير محدد",
        verbose_name="الصف",
    )

    school_type = models.CharField(
        max_length=50,
        default="غير محدد",
        verbose_name="نوع التعليم",
    )

    student_phone = models.CharField(
        max_length=20,
        default="",
        verbose_name="رقم الطالب",
    )

    parent_phone = models.CharField(
        max_length=20,
        default="",
        verbose_name="رقم ولي الأمر",
    )

    is_active = models.BooleanField(
        default=False,
        verbose_name="الحساب مفعل",
    )

    suspension_reason = models.TextField(
        blank=True,
        verbose_name="سبب إيقاف الحساب",
    )

    selected_skills = models.JSONField(
        default=list,
        blank=True,
        verbose_name="المهارات المختارة عند التسجيل",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    def __str__(self):
        return f"{self.student_name} ({self.grade})"


# ====================================================
# Grade Settings
# ====================================================

class GradeSetting(models.Model):

    GRADES = [
        ("الصف الأول الابتدائي", "الصف الأول الابتدائي"),
        ("الصف الثاني الابتدائي", "الصف الثاني الابتدائي"),
        ("الصف الثالث الابتدائي", "الصف الثالث الابتدائي"),
        ("الصف الرابع الابتدائي", "الصف الرابع الابتدائي"),
        ("الصف الخامس الابتدائي", "الصف الخامس الابتدائي"),
        ("الصف السادس الابتدائي", "الصف السادس الابتدائي"),
        ("الصف الأول الإعدادي", "الصف الأول الإعدادي"),
        ("الصف الثاني الإعدادي", "الصف الثاني الإعدادي"),
        ("الصف الثالث الإعدادي", "الصف الثالث الإعدادي"),
    ]

    grade = models.CharField(
        max_length=100,
        choices=GRADES,
        unique=True,
        verbose_name="الصف",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="الصف متاح",
    )

    monthly_subject_price = models.PositiveIntegerField(
        default=0,
        verbose_name="سعر المادة شهريًا",
    )

    full_term_price = models.PositiveIntegerField(
        default=0,
        verbose_name="سعر الترم الكامل",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        ordering = ["grade"]
        verbose_name = "إعداد الصف"
        verbose_name_plural = "إعدادات الصفوف"

    def __str__(self):
        status = "متاح" if self.is_active else "غير متاح"
        return f"{self.grade} - {status}"


# ====================================================
# Available Subject
# ====================================================

class AvailableSubject(models.Model):

    SCHOOL_TYPES = [
        ("عربي", "عربي"),
        ("لغات", "لغات"),
    ]

    grade = models.ForeignKey(
        GradeSetting,
        on_delete=models.CASCADE,
        related_name="available_subjects",
        verbose_name="الصف",
    )

    school_type = models.CharField(
        max_length=50,
        choices=SCHOOL_TYPES,
        verbose_name="نوع التعليم",
    )

    subject_name = models.CharField(
        max_length=100,
        verbose_name="اسم المادة",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="المادة متاحة",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "grade",
                    "school_type",
                    "subject_name",
                ],
                name="unique_available_subject",
            )
        ]

        ordering = ["subject_name"]

        verbose_name = "مادة متاحة"
        verbose_name_plural = "المواد المتاحة"

    def __str__(self):
        status = "متاحة" if self.is_active else "غير متاحة"

        return (
            f"{self.grade.grade} - "
            f"{self.school_type} - "
            f"{self.subject_name} - "
            f"{status}"
        )


# ====================================================
# Skill
# ====================================================

class Skill(models.Model):

    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="اسم المهارة",
    )

    description = models.TextField(
        blank=True,
        verbose_name="وصف المهارة",
    )

    course_price = models.PositiveIntegerField(
        default=0,
        verbose_name="سعر الكورس كامل",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="المهارة متاحة",
    )

    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="required_for",
        verbose_name="المتطلبات السابقة",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "مهارة"
        verbose_name_plural = "المهارات"

    def __str__(self):
        status = "متاحة" if self.is_active else "غير متاحة"

        return (
            f"{self.name} - "
            f"{self.course_price} جنيه - "
            f"{status}"
        )


# ====================================================
# Skill Lesson
# ====================================================

class SkillLesson(models.Model):

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name="المهارة",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان الدرس",
    )

    description = models.TextField(
        blank=True,
        verbose_name="وصف الدرس",
    )

    video = models.FileField(
        upload_to="skill_lessons/",
        blank=True,
        null=True,
        verbose_name="فيديو الدرس",
    )

    order = models.PositiveIntegerField(
        default=1,
        verbose_name="ترتيب الدرس",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="الدرس متاح",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "درس مهارة"
        verbose_name_plural = "دروس المهارات"

    def __str__(self):
        return f"{self.skill.name} - {self.title}"


# ====================================================
# Skill Homework
# ====================================================

class SkillHomework(models.Model):

    HOMEWORK_TYPES = [
        ("electronic", "واجب إلكتروني"),
        ("paper", "واجب ورقي"),
    ]

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="homeworks",
        verbose_name="المهارة",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان الواجب",
    )

    homework_type = models.CharField(
        max_length=20,
        choices=HOMEWORK_TYPES,
        default="electronic",
        verbose_name="نوع الواجب",
    )

    description = models.TextField(
        blank=True,
        verbose_name="وصف الواجب",
    )

    file = models.FileField(
        upload_to="skill_homework/",
        blank=True,
        null=True,
        verbose_name="ملف الواجب",
    )

    total_marks = models.PositiveIntegerField(
        default=0,
        verbose_name="إجمالي الدرجات",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإضافة",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="الواجب متاح",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "واجب مهارة"
        verbose_name_plural = "واجبات المهارات"

    def __str__(self):
        return f"{self.skill.name} - {self.title}"


# ====================================================
# Skill Homework Question
# ====================================================

class SkillHomeworkQuestion(models.Model):

    homework = models.ForeignKey(
        SkillHomework,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="الواجب",
    )

    question_text = models.TextField(
        verbose_name="السؤال",
    )

    choice_a = models.CharField(
        max_length=500,
        verbose_name="الاختيار الأول",
    )

    choice_b = models.CharField(
        max_length=500,
        verbose_name="الاختيار الثاني",
    )

    choice_c = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="الاختيار الثالث",
    )

    choice_d = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="الاختيار الرابع",
    )

    CORRECT_CHOICES = [
        ("a", "الاختيار الأول"),
        ("b", "الاختيار الثاني"),
        ("c", "الاختيار الثالث"),
        ("d", "الاختيار الرابع"),
    ]

    correct_answer = models.CharField(
        max_length=1,
        choices=CORRECT_CHOICES,
        verbose_name="الإجابة الصحيحة",
    )

    mark = models.PositiveIntegerField(
        default=1,
        verbose_name="درجة السؤال",
    )

    order = models.PositiveIntegerField(
        default=1,
        verbose_name="ترتيب السؤال",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإضافة",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "سؤال واجب مهارة"
        verbose_name_plural = "أسئلة واجبات المهارات"

    def __str__(self):
        return (
            f"{self.homework.title} - "
            f"سؤال {self.order}"
        )


# ====================================================
# Skill Homework Submission
# ====================================================

class SkillHomeworkSubmission(models.Model):

    STATUS_CHOICES = [
        ("submitted", "تم التسليم"),
        ("graded", "تم التصحيح"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="skill_homework_submissions",
        verbose_name="الطالب",
    )

    homework = models.ForeignKey(
        SkillHomework,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="الواجب",
    )

    uploaded_file = models.FileField(
        upload_to="skill_homework_submissions/",
        blank=True,
        null=True,
        verbose_name="ملف إجابة الطالب",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="submitted",
        verbose_name="الحالة",
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="وقت التسليم",
    )

    graded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="وقت التصحيح",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "homework"],
                name="unique_student_skill_homework_submission",
            )
        ]

        verbose_name = "تسليم واجب مهارة"
        verbose_name_plural = "تسليمات واجبات المهارات"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.homework.title}"
        )


# ====================================================
# Skill Homework Answer
# ====================================================

class SkillHomeworkAnswer(models.Model):

    submission = models.ForeignKey(
        SkillHomeworkSubmission,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="التسليم",
    )

    question = models.ForeignKey(
        SkillHomeworkQuestion,
        on_delete=models.CASCADE,
        related_name="student_answers",
        verbose_name="السؤال",
    )

    selected_answer = models.CharField(
        max_length=1,
        blank=True,
        verbose_name="إجابة الطالب",
    )

    is_correct = models.BooleanField(
        default=False,
        verbose_name="الإجابة صحيحة",
    )

    mark_obtained = models.PositiveIntegerField(
        default=0,
        verbose_name="الدرجة المحصلة",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "question"],
                name="unique_skill_submission_question_answer",
            )
        ]

        verbose_name = "إجابة واجب مهارة"
        verbose_name_plural = "إجابات واجبات المهارات"

    def __str__(self):
        return (
            f"{self.submission.student.student_name} - "
            f"{self.question.homework.title}"
        )


# ====================================================
# Skill Homework Result
# ====================================================

class SkillHomeworkResult(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="skill_homework_results",
        verbose_name="الطالب",
    )

    homework = models.ForeignKey(
        SkillHomework,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="الواجب",
    )

    score = models.FloatField(
        default=0,
        verbose_name="الدرجة",
    )

    max_score = models.FloatField(
        default=0,
        verbose_name="الدرجة النهائية",
    )

    feedback = models.TextField(
        blank=True,
        verbose_name="ملاحظات",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ النتيجة",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "homework"],
                name="unique_student_skill_homework_result",
            )
        ]

        verbose_name = "نتيجة واجب مهارة"
        verbose_name_plural = "نتائج واجبات المهارات"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.homework.title}"
        )


# ====================================================
# Skill Subscription
# ====================================================

class SkillSubscription(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="skill_subscriptions",
        verbose_name="الطالب",
    )

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name="المهارة",
    )

    start_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاريخ البداية",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="مفعلة",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "skill"],
                name="unique_student_skill_subscription",
            )
        ]

        verbose_name = "اشتراك مهارة"
        verbose_name_plural = "اشتراكات المهارات"

    def __str__(self):
        return f"{self.student.student_name} - {self.skill.name}"


# ====================================================
# Platform Settings
# ====================================================

class PlatformSettings(models.Model):

    name = models.CharField(
        max_length=100,
        default="إعدادات المنصة",
        unique=True,
        verbose_name="اسم الإعدادات",
    )

    curriculum_enabled = models.BooleanField(
        default=True,
        verbose_name="المنهج مفعل",
    )

    curriculum_available_in_vacation = models.BooleanField(
        default=False,
        verbose_name="المنهج متاح في الإجازة",
    )

    skills_available_in_vacation = models.BooleanField(
        default=True,
        verbose_name="المهارات متاحة في الإجازة",
    )

    vacation_start_month = models.PositiveIntegerField(
        default=6,
        verbose_name="شهر بداية الإجازة",
    )

    vacation_end_month = models.PositiveIntegerField(
        default=9,
        verbose_name="شهر نهاية الإجازة",
    )

    whatsapp_number = models.CharField(
        max_length=30,
        default="01555266046",
        verbose_name="رقم واتساب الدعم",
    )

    vodafone_cash_number = models.CharField(
        max_length=30,
        default="01551174945",
        verbose_name="رقم فودافون كاش",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        verbose_name = "إعدادات المنصة"
        verbose_name_plural = "إعدادات المنصة"

    def __str__(self):
        return self.name

    @classmethod
    def get_settings(cls):
        settings_obj = cls.objects.first()

        if settings_obj is None:
            settings_obj = cls.objects.create(
                name="إعدادات المنصة"
            )

        return settings_obj

    def is_vacation_now(self):
        current_month = timezone.localtime().month

        start = self.vacation_start_month
        end = self.vacation_end_month

        if start <= end:
            return start <= current_month <= end

        return (
            current_month >= start
            or current_month <= end
        )

    def curriculum_is_open_now(self):

        if not self.curriculum_enabled:
            return False

        if not self.is_vacation_now():
            return True

        return self.curriculum_available_in_vacation

    def skills_are_open_now(self):

        if not self.is_vacation_now():
            return True

        return self.skills_available_in_vacation


# ====================================================
# ClassRoom
# ====================================================

class ClassRoom(models.Model):

    name = models.CharField(
        max_length=100,
        verbose_name="اسم الفصل",
    )

    def __str__(self):
        return self.name


# ====================================================
# Subscription Request
# ====================================================

class SubscriptionRequest(models.Model):

    STATUS_CHOICES = [
        ("pending", "قيد المراجعة"),
        ("approved", "مقبول"),
        ("rejected", "مرفوض"),
    ]

    SUBSCRIPTION_TYPES = [
        ("subjects", "مواد معينة"),
        ("full_term", "الترم كامل"),
        ("skills", "مهارات"),
        ("mixed", "منهج + مهارات"),
    ]

    REQUEST_TYPES = [
        ("initial", "اشتراك أول مرة"),
        ("addition", "إضافة مواد أو مهارات"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="subscription_requests",
        verbose_name="الطالب",
    )

    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPES,
        default="initial",
        verbose_name="نوع الطلب",
    )

    amount = models.PositiveIntegerField(
        default=0,
        verbose_name="الإجمالي",
    )

    curriculum_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="سعر المنهج",
    )

    skills_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="سعر المهارات",
    )

    subscription_type = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_TYPES,
        default="subjects",
        verbose_name="نوع الاشتراك",
    )

    selected_subjects = models.JSONField(
        default=list,
        blank=True,
        verbose_name="المواد المختارة",
    )

    selected_skills = models.JSONField(
        default=list,
        blank=True,
        verbose_name="المهارات المختارة",
    )

    transfer_image = models.ImageField(
        upload_to="payments/",
        verbose_name="صورة التحويل",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="الحالة",
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name="سبب الرفض",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاريخ المعالجة",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "طلب اشتراك"
        verbose_name_plural = "طلبات الاشتراك"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.get_status_display()} - "
            f"{self.amount} جنيه"
        )


# ====================================================
# Subject Subscription
# ====================================================

class SubjectSubscription(models.Model):

    PLAN_TYPES = [
        ("monthly", "شهري"),
        ("full_term", "الترم كامل"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="subject_subscriptions",
        verbose_name="الطالب",
    )

    subject = models.CharField(
        max_length=100,
        verbose_name="المادة",
    )

    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPES,
        default="monthly",
        verbose_name="نوع الخطة",
    )

    start_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاريخ البداية",
    )

    end_date = models.DateTimeField(
        verbose_name="تاريخ النهاية",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )

    watched_lessons = models.PositiveIntegerField(
        default=0,
        verbose_name="الحصص المشاهدة",
    )

    max_lessons = models.PositiveIntegerField(
        default=4,
        verbose_name="الحد الأقصى للحصص",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "student",
                    "subject",
                    "is_active",
                ]
            ),
            models.Index(
                fields=["end_date"]
            ),
        ]

        verbose_name = "اشتراك مادة"
        verbose_name_plural = "اشتراكات المواد"

    def __str__(self):
        return f"{self.student.student_name} - {self.subject}"

    @property
    def is_expired(self):
        return timezone.now() >= self.end_date

    @property
    def lessons_remaining(self):
        if self.max_lessons == 0:
            return None

        return max(
            self.max_lessons - self.watched_lessons,
            0,
        )

    @property
    def remaining_label(self):
        if (
            self.plan_type == "full_term"
            or self.max_lessons == 0
        ):
            return "مفتوح"

        return str(self.lessons_remaining)

    @property
    def is_usable(self):

        if not self.is_active:
            return False

        if self.is_expired:
            return False

        if (
            self.max_lessons > 0
            and self.watched_lessons >= self.max_lessons
        ):
            return False

        return True

    def check_expired(self):

        if self.is_active and self.is_expired:

            self.is_active = False

            self.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

            return True

        return False


# ====================================================
# Study Material
# ====================================================

class StudyMaterial(models.Model):

    MATERIAL_TYPES = [
        ("image", "صورة"),
        ("video", "فيديو"),
        ("exam", "امتحان"),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name="العنوان",
    )

    grade = models.CharField(
        max_length=100,
        verbose_name="الصف",
    )

    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPES,
        verbose_name="نوع المحتوى",
    )

    file = models.FileField(
        upload_to="study_materials/",
        verbose_name="الملف",
    )

    description = models.TextField(
        blank=True,
        verbose_name="الوصف",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )

    def __str__(self):
        return f"{self.title} - {self.grade}"


# ====================================================
# Lesson
# ====================================================

class Lesson(models.Model):

    GRADES = GradeSetting.GRADES

    SCHOOL_TYPES = [
        ("عربي", "عربي"),
        ("لغات", "لغات"),
    ]

    SUBJECTS = [
        ("عربي", "عربي"),
        ("رياضيات", "رياضيات"),
        ("علوم", "علوم"),
        ("دراسات", "دراسات"),
        ("إنجليزي", "إنجليزي"),
        ("Math", "Math"),
        ("English", "English"),
        ("Science", "Science"),
        ("English Plus", "English Plus"),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان الحصة",
    )

    grade = models.CharField(
        max_length=100,
        choices=GRADES,
        verbose_name="الصف",
    )

    school_type = models.CharField(
        max_length=50,
        choices=SCHOOL_TYPES,
        verbose_name="نوع التعليم",
    )

    subject = models.CharField(
        max_length=100,
        choices=SUBJECTS,
        verbose_name="المادة",
    )

    video = models.FileField(
        upload_to="lessons_videos/",
        blank=True,
        null=True,
        verbose_name="فيديو الحصة",
    )

    description = models.TextField(
        blank=True,
        verbose_name="وصف الحصة",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإضافة",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="الحصة متاحة",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "grade",
                    "school_type",
                    "is_active",
                ]
            ),
            models.Index(
                fields=[
                    "subject",
                    "-created_at",
                ]
            ),
        ]

        ordering = ["created_at"]

        verbose_name = "حصة"
        verbose_name_plural = "الحصص"

    def __str__(self):
        return (
            f"{self.title} - "
            f"{self.grade} - "
            f"{self.school_type} - "
            f"{self.subject}"
        )


# ====================================================
# Lesson Watch Statistics
# ====================================================

class LessonWatchStat(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="watch_stats",
        verbose_name="الطالب",
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="watch_stats",
        verbose_name="الحصة",
    )

    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name="عدد المشاهدات",
    )

    watch_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name="وقت المشاهدة بالثواني",
    )

    last_position = models.FloatField(
        default=0.0,
        verbose_name="آخر مكان",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "lesson",
                ],
                name="unique_student_lesson_watch_stat",
            )
        ]

        verbose_name = "إحصائيات مشاهدة"
        verbose_name_plural = "إحصائيات المشاهدة"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.lesson.title}"
        )


# ====================================================
# Homework
# ====================================================

class Homework(models.Model):

    HOMEWORK_TYPES = [
        ("electronic", "واجب إلكتروني"),
        ("paper", "واجب ورقي"),
    ]

    GRADES = Lesson.GRADES
    SCHOOL_TYPES = Lesson.SCHOOL_TYPES
    SUBJECTS = Lesson.SUBJECTS

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان الواجب",
    )

    homework_type = models.CharField(
        max_length=20,
        choices=HOMEWORK_TYPES,
        default="electronic",
        verbose_name="نوع الواجب",
    )

    description = models.TextField(
        blank=True,
        verbose_name="وصف الواجب",
    )

    grade = models.CharField(
        max_length=100,
        choices=GRADES,
        verbose_name="الصف",
    )

    school_type = models.CharField(
        max_length=50,
        choices=SCHOOL_TYPES,
        verbose_name="نوع التعليم",
    )

    subject = models.CharField(
        max_length=100,
        choices=SUBJECTS,
        verbose_name="المادة",
    )

    file = models.FileField(
        upload_to="homework/",
        blank=True,
        null=True,
        verbose_name="ملف الواجب",
    )

    total_marks = models.PositiveIntegerField(
        default=0,
        verbose_name="إجمالي الدرجات",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "واجب"
        verbose_name_plural = "الواجبات"

    def __str__(self):
        return (
            f"{self.title} - "
            f"{self.subject} - "
            f"{self.grade}"
        )


# ====================================================
# Homework Questions
# ====================================================

class HomeworkQuestion(models.Model):

    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="الواجب",
    )

    question_text = models.TextField(
        verbose_name="السؤال",
    )

    choice_a = models.CharField(
        max_length=500,
        verbose_name="الاختيار الأول",
    )

    choice_b = models.CharField(
        max_length=500,
        verbose_name="الاختيار الثاني",
    )

    choice_c = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="الاختيار الثالث",
    )

    choice_d = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="الاختيار الرابع",
    )

    CORRECT_CHOICES = [
        ("a", "الاختيار الأول"),
        ("b", "الاختيار الثاني"),
        ("c", "الاختيار الثالث"),
        ("d", "الاختيار الرابع"),
    ]

    correct_answer = models.CharField(
        max_length=1,
        choices=CORRECT_CHOICES,
        verbose_name="الإجابة الصحيحة",
    )

    mark = models.PositiveIntegerField(
        default=1,
        verbose_name="درجة السؤال",
    )

    order = models.PositiveIntegerField(
        default=1,
        verbose_name="ترتيب السؤال",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    class Meta:
        ordering = ["order", "id"]

        verbose_name = "سؤال واجب"
        verbose_name_plural = "أسئلة الواجبات"

    def __str__(self):
        return (
            f"{self.homework.title} - "
            f"سؤال {self.order}"
        )


# ====================================================
# Homework Submission
# ====================================================

class HomeworkSubmission(models.Model):

    STATUS_CHOICES = [
        ("submitted", "تم التسليم"),
        ("pending", "قيد التصحيح"),
        ("graded", "تم التصحيح"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="homework_submissions",
        verbose_name="الطالب",
    )

    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="الواجب",
    )

    uploaded_file = models.FileField(
        upload_to="homework_submissions/",
        blank=True,
        null=True,
        verbose_name="إجابة الطالب",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="submitted",
        verbose_name="حالة التسليم",
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="وقت التسليم",
    )

    graded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="وقت التصحيح",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "homework",
                ],
                name="unique_student_homework_submission",
            )
        ]

        verbose_name = "تسليم واجب"
        verbose_name_plural = "تسليمات الواجبات"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.homework.title}"
        )


# ====================================================
# Homework Answer
# ====================================================

class HomeworkAnswer(models.Model):

    submission = models.ForeignKey(
        HomeworkSubmission,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="التسليم",
    )

    question = models.ForeignKey(
        HomeworkQuestion,
        on_delete=models.CASCADE,
        related_name="student_answers",
        verbose_name="السؤال",
    )

    selected_answer = models.CharField(
        max_length=1,
        blank=True,
        verbose_name="إجابة الطالب",
    )

    is_correct = models.BooleanField(
        default=False,
        verbose_name="الإجابة صحيحة",
    )

    mark_obtained = models.PositiveIntegerField(
        default=0,
        verbose_name="الدرجة المحصلة",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "submission",
                    "question",
                ],
                name="unique_submission_question_answer",
            )
        ]

        verbose_name = "إجابة واجب"
        verbose_name_plural = "إجابات الواجبات"

    def __str__(self):
        return (
            f"{self.submission.student.student_name} - "
            f"{self.question.homework.title}"
        )


# ====================================================
# Homework Result
# ====================================================

class HomeworkResult(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="homework_results",
        verbose_name="الطالب",
    )

    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="الواجب",
    )

    score = models.FloatField(
        default=0,
        verbose_name="الدرجة",
    )

    max_score = models.FloatField(
        default=0,
        verbose_name="الدرجة النهائية",
    )

    feedback = models.TextField(
        blank=True,
        verbose_name="ملاحظات المدرس",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ النتيجة",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "homework",
                ],
                name="unique_student_homework_result",
            )
        ]

        verbose_name = "نتيجة واجب"
        verbose_name_plural = "نتائج الواجبات"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.homework.title}"
        )


# ====================================================
# Exam
# ====================================================

class Exam(models.Model):

    GRADES = Lesson.GRADES
    SCHOOL_TYPES = Lesson.SCHOOL_TYPES
    SUBJECTS = Lesson.SUBJECTS

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان الامتحان",
    )

    description = models.TextField(
        blank=True,
        verbose_name="وصف الامتحان",
    )

    grade = models.CharField(
        max_length=100,
        choices=GRADES,
        verbose_name="الصف",
    )

    school_type = models.CharField(
        max_length=50,
        choices=SCHOOL_TYPES,
        verbose_name="نوع التعليم",
    )

    subject = models.CharField(
        max_length=100,
        choices=SUBJECTS,
        verbose_name="المادة",
    )

    file = models.FileField(
        upload_to="exams/",
        blank=True,
        null=True,
        verbose_name="ملف الامتحان",
    )

    total_marks = models.PositiveIntegerField(
        default=100,
        verbose_name="إجمالي الدرجات",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "امتحان"
        verbose_name_plural = "الامتحانات"

    def __str__(self):
        return (
            f"{self.title} - "
            f"{self.subject} - "
            f"{self.grade}"
        )


# ====================================================
# Exam Result
# ====================================================

class ExamResult(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="exam_results",
        verbose_name="الطالب",
    )

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="الامتحان",
    )

    score = models.FloatField(
        default=0,
        verbose_name="الدرجة",
    )

    feedback = models.TextField(
        blank=True,
        verbose_name="ملاحظات المدرس",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ النتيجة",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "exam",
                ],
                name="unique_student_exam_result",
            )
        ]

        verbose_name = "نتيجة امتحان"
        verbose_name_plural = "نتائج الامتحانات"

    def __str__(self):
        return (
            f"{self.student.student_name} - "
            f"{self.exam.title}"
        )


# ====================================================
# AI Conversation
# ====================================================

class AIConversation(models.Model):

    STATUS_CHOICES = [
        ("open", "مفتوحة"),
        ("closed", "مغلقة"),
    ]

    CONTEXT_CHOICES = [
        ("subject", "منهج / مادة"),
        ("skill", "مهارة"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
        verbose_name="الطالب",
    )

    context_type = models.CharField(
        max_length=20,
        choices=CONTEXT_CHOICES,
        default="subject",
        verbose_name="نوع المحادثة",
    )

    subject = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="المادة",
    )

    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations",
        verbose_name="المهارة",
    )

    title = models.CharField(
        max_length=200,
        default="محادثة جديدة",
        verbose_name="عنوان المحادثة",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
        verbose_name="الحالة",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الإنشاء",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخر تحديث",
    )

    class Meta:
        ordering = ["-updated_at"]

        verbose_name = "محادثة AI"
        verbose_name_plural = "محادثات AI"

    def __str__(self):
        context_name = self.subject

        if self.skill:
            context_name = self.skill.name

        return (
            f"{self.student.student_name} - "
            f"{context_name or self.title}"
        )


# ====================================================
# AI Message
# ====================================================

class AIMessage(models.Model):

    SENDER_CHOICES = [
        ("student", "الطالب"),
        ("ai", "المساعد"),
        ("admin", "الإدارة"),
    ]

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="المحادثة",
    )

    sender_type = models.CharField(
        max_length=20,
        choices=SENDER_CHOICES,
        verbose_name="المرسل",
    )

    message = models.TextField(
        blank=True,
        verbose_name="الرسالة",
    )

    image = models.ImageField(
        upload_to="ai_chat/",
        blank=True,
        null=True,
        verbose_name="الصورة المرسلة",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاريخ الرسالة",
    )

    class Meta:
        ordering = ["created_at"]

        verbose_name = "رسالة AI"
        verbose_name_plural = "رسائل AI"

    def __str__(self):
        return (
            f"{self.conversation.student.student_name} - "
            f"{self.sender_type}"
        )


# ====================================================
# Signal
# ====================================================

@receiver(
    post_save,
    sender=SubscriptionRequest,
)
def activate_subscription_on_approval(
    sender,
    instance,
    created,
    **kwargs,
):

    if (
        instance.status != "approved"
        or instance.processed_at is not None
    ):
        return

    student = instance.student

    with transaction.atomic():

        student.is_active = True
        student.suspension_reason = ""

        student.save(
            update_fields=[
                "is_active",
                "suspension_reason",
                "updated_at",
            ]
        )

        if (
            student.user
            and not student.user.is_active
        ):

            student.user.is_active = True

            student.user.save(
                update_fields=["is_active"]
            )

        start_date = timezone.now()

        is_full_term = (
            instance.subscription_type
            == "full_term"
        )

        if is_full_term:

            plan_type = "full_term"
            max_lessons = 0

            end_date = timezone.make_aware(
                datetime(
                    2027,
                    5,
                    15,
                    23,
                    59,
                    59,
                ),
                timezone.get_current_timezone(),
            )

        else:

            plan_type = "monthly"
            max_lessons = 4

            end_date = (
                start_date
                + timedelta(days=30)
            )

        curriculum_types = [
            "subjects",
            "full_term",
            "mixed",
        ]

        if (
            instance.subscription_type
            in curriculum_types
        ):

            subjects = list(
                dict.fromkeys(
                    instance.selected_subjects
                    or []
                )
            )

            for subject_name in subjects:

                SubjectSubscription.objects.filter(
                    student=student,
                    subject=subject_name,
                    is_active=True,
                ).update(
                    is_active=False
                )

                SubjectSubscription.objects.create(
                    student=student,
                    subject=subject_name,
                    plan_type=plan_type,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,
                    watched_lessons=0,
                    max_lessons=max_lessons,
                )

        skills = list(
            dict.fromkeys(
                instance.selected_skills
                or []
            )
        )

        for skill_name in skills:

            skill = Skill.objects.filter(
                name=skill_name,
                is_active=True,
            ).first()

            if not skill:
                continue

            SkillSubscription.objects.filter(
                student=student,
                skill=skill,
                is_active=True,
            ).update(
                is_active=False
            )

            SkillSubscription.objects.create(
                student=student,
                skill=skill,
                start_date=start_date,
                is_active=True,
            )

        SubscriptionRequest.objects.filter(
            pk=instance.pk,
        ).update(
            processed_at=timezone.now(),
        )

