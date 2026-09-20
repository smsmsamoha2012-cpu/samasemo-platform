from django import forms

from .models import (
    GradeSetting,
    Skill,
    Student,
)


# ====================================================
# إنشاء إعدادات الصفوف تلقائيًا
# ====================================================

def ensure_grade_settings():

    for grade, _ in GradeSetting.GRADES:

        GradeSetting.objects.get_or_create(
            grade=grade,
            defaults={
                "is_active": True,
            },
        )


# ====================================================
# Student Form
# ====================================================

class StudentForm(forms.ModelForm):

    initial_skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="المهارات",
    )

    class Meta:

        model = Student

        fields = [
            "student_name",
            "grade",
            "school_type",
            "student_phone",
            "parent_phone",
        ]

        labels = {
            "student_name": "اسم الطالب الثلاثي",
            "grade": "الصف الدراسي",
            "school_type": "نوع التعليم",
            "student_phone": "رقم تليفون الطالب",
            "parent_phone": "رقم تليفون ولي الأمر",
        }

        widgets = {

            "student_name": forms.TextInput(
                attrs={
                    "placeholder": (
                        "اكتب الاسم الثلاثي"
                    ),
                }
            ),

            "student_phone": forms.TextInput(
                attrs={
                    "placeholder": (
                        "اكتب رقم تليفون الطالب"
                    ),
                }
            ),

            "parent_phone": forms.TextInput(
                attrs={
                    "placeholder": (
                        "اكتب رقم تليفون ولي الأمر"
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):

        super().__init__(
            *args,
            **kwargs,
        )

        ensure_grade_settings()

        self.fields[
            "initial_skills"
        ].queryset = (
            Skill.objects.filter(
                is_active=True
            )
            .prefetch_related(
                "prerequisites"
            )
            .order_by("name")
        )

    # =================================================
    # اسم الطالب
    # =================================================

    def clean_student_name(self):

        name = (
            self.cleaned_data.get(
                "student_name",
                "",
            )
            .strip()
        )

        if len(name.split()) < 3:

            raise forms.ValidationError(
                "من فضلك اكتب الاسم الثلاثي للطالب ❌"
            )

        return name

    # =================================================
    # رقم الطالب
    # =================================================

    def clean_student_phone(self):

        phone = (
            self.cleaned_data.get(
                "student_phone",
                "",
            )
            .strip()
        )

        if not phone:

            raise forms.ValidationError(
                "من فضلك اكتب رقم تليفون الطالب."
            )

        if Student.objects.filter(
            student_phone=phone
        ).exists():

            raise forms.ValidationError(
                "رقم تليفون الطالب مسجل بالفعل."
            )

        return phone

    # =================================================
    # الصف
    # =================================================

    def clean_grade(self):

        grade = self.cleaned_data.get(
            "grade"
        )

        if not grade:

            raise forms.ValidationError(
                "اختاري الصف الدراسي."
            )

        setting = (
            GradeSetting.objects.filter(
                grade=grade
            )
            .first()
        )

        if (
            setting
            and not setting.is_active
        ):

            raise forms.ValidationError(
                "هذا الصف غير متاح للتسجيل حاليًا."
            )

        return grade

    # =================================================
    # نوع التعليم
    # =================================================

    def clean_school_type(self):

        school_type = (
            self.cleaned_data.get(
                "school_type"
            )
        )

        if school_type not in [
            "عربي",
            "لغات",
        ]:

            raise forms.ValidationError(
                "اختاري نوع التعليم."
            )

        return school_type

    # =================================================
    # التحقق من المهارات
    # =================================================

    def clean(self):

        cleaned_data = super().clean()

        selected_skills = list(
            cleaned_data.get(
                "initial_skills"
            )
            or []
        )

        selected_ids = {
            skill.id
            for skill in selected_skills
        }

        for skill in selected_skills:

            for prerequisite in (
                skill.prerequisites.all()
            ):

                if (
                    prerequisite.id
                    not in selected_ids
                ):

                    raise forms.ValidationError(
                        f"لا يمكن اختيار "
                        f"{skill.name} "
                        f"إلا بعد اختيار "
                        f"{prerequisite.name} "
                        f"أولًا."
                    )

                if not prerequisite.is_active:

                    raise forms.ValidationError(
                        f"المهارة المطلوبة "
                        f"{prerequisite.name} "
                        f"غير متاحة حاليًا."
                    )

        return cleaned_data