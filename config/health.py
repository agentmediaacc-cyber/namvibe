from django.http import HttpResponse


def healthz(_request):
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")
