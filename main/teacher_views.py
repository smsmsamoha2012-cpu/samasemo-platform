
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect


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
            password=password
        )

        if user is not None and user.is_staff:
            login(request, user)
            return redirect("/teacher/dashboard/")

        error = "اسم المستخدم أو كلمة المرور غير صحيحة، أو الحساب غير مصرح له بالدخول."

    return render(
        request,
        "main/teacher_login.html",
        {
            "error": error,
        }
    )


def teacher_dashboard(request):

    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect("/teacher/")

    return render(
        request,
        "main/teacher_dashboard.html"
    )


def teacher_logout(request):

    logout(request)

    return redirect("/")
