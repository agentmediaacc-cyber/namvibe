from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include

def home(request):
    return HttpResponse("""
    <html>
      <head>
        <title>Namvibe</title>
        <style>
          body { font-family: Arial, sans-serif; background:#0f172a; color:white; padding:40px; text-align:center; }
          .box { max-width:700px; margin:60px auto; background:#111827; border-radius:18px; padding:40px; }
        </style>
      </head>
      <body>
        <div class="box">
          <h1>Namvibe is live 🚀</h1>
          <p>Main route is working from config/urls.py.</p>
        </div>
      </body>
    </html>
    """)

urlpatterns = [
    path("", home),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("posts/", include("posts.urls")),
    path("live/", include("live.urls")),
    path("livestream/", include("livestream.urls")),
]
