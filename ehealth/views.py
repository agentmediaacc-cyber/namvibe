from django.shortcuts import render

def dashboard(request):
    return render(request, "ehealth/dashboard.html")

def profile(request):
    return render(request, "ehealth/profile.html")

def card(request):
    return render(request, "ehealth/simple.html", {"title": "eHealth Card", "empty": "Your digital health card will appear here."})

def appointments(request):
    return render(request, "ehealth/simple.html", {"title": "Appointments", "empty": "No appointments yet."})

def messages(request):
    return render(request, "ehealth/simple.html", {"title": "Messages", "empty": "No health messages yet."})

def consent(request):
    return render(request, "ehealth/simple.html", {"title": "Consent", "empty": "No consent records yet."})
