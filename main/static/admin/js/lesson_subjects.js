(function () {


function setupLessonSubjects() {

    const gradeField = document.getElementById("id_grade");
    const schoolTypeField = document.getElementById("id_school_type");
    const subjectField = document.getElementById("id_subject");

    if (!gradeField || !schoolTypeField || !subjectField) {
        return;
    }


    const subjects = {

        primary_1_3: {

            "عربي": [
                ["عربي", "عربي"],
                ["رياضيات", "رياضيات"],
                ["إنجليزي", "إنجليزي"]
            ],

            "لغات": [
                ["عربي", "عربي"],
                ["Math", "Math"],
                ["English", "English"],
                ["English Plus", "English Plus"]
            ]

        },


        primary_4_6: {

            "عربي": [
                ["عربي", "عربي"],
                ["رياضيات", "رياضيات"],
                ["علوم", "علوم"],
                ["دراسات", "دراسات"],
                ["إنجليزي", "إنجليزي"]
            ],

            "لغات": [
                ["عربي", "عربي"],
                ["دراسات", "دراسات"],
                ["English", "English"],
                ["Math", "Math"],
                ["Science", "Science"],
                ["English Plus", "English Plus"]
            ]

        },


        preparatory: {

            "عربي": [
                ["عربي", "عربي"],
                ["رياضيات", "رياضيات"],
                ["علوم", "علوم"],
                ["دراسات", "دراسات"],
                ["إنجليزي", "إنجليزي"]
            ],

            "لغات": [
                ["عربي", "عربي"],
                ["دراسات", "دراسات"],
                ["English", "English"],
                ["Math", "Math"],
                ["Science", "Science"],
                ["English Plus", "English Plus"]
            ]

        }

    };


    function getCategory(grade) {

        if (
            grade === "الصف الأول الابتدائي" ||
            grade === "الصف الثاني الابتدائي" ||
            grade === "الصف الثالث الابتدائي"
        ) {
            return "primary_1_3";
        }


        if (
            grade === "الصف الرابع الابتدائي" ||
            grade === "الصف الخامس الابتدائي" ||
            grade === "الصف السادس الابتدائي"
        ) {
            return "primary_4_6";
        }


        if (
            grade === "الصف الأول الإعدادي" ||
            grade === "الصف الثاني الإعدادي" ||
            grade === "الصف الثالث الإعدادي"
        ) {
            return "preparatory";
        }


        return null;
    }


    function updateSubjects() {

        const grade = gradeField.value;
        const schoolType = schoolTypeField.value;
        const category = getCategory(grade);

        const currentValue = subjectField.value;

        subjectField.innerHTML = "";


        const firstOption = document.createElement("option");

        firstOption.value = "";
        firstOption.textContent = "اختاري المادة";

        subjectField.appendChild(firstOption);


        if (
            !category ||
            !schoolType ||
            !subjects[category] ||
            !subjects[category][schoolType]
        ) {

            subjectField.disabled = true;

            return;
        }


        subjectField.disabled = false;


        subjects[category][schoolType].forEach(
            function (subject) {

                const option = document.createElement("option");

                option.value = subject[0];
                option.textContent = subject[1];

                if (subject[0] === currentValue) {
                    option.selected = true;
                }

                subjectField.appendChild(option);
            }
        );
    }


    gradeField.addEventListener(
        "change",
        updateSubjects
    );


    schoolTypeField.addEventListener(
        "change",
        updateSubjects
    );


    updateSubjects();
}


if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        setupLessonSubjects
    );

} else {

    setupLessonSubjects();

}


})();
