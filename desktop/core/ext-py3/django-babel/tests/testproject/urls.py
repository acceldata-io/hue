import time

from django.urls import re_path
from django.shortcuts import render
from django.utils.timezone import now


def test_view(request):
    return render(request, 'test.txt', {
        'date': now(),
        'number': time.time(),
        'locale': request.locale,
    })


urlpatterns = [
    re_path('^$', test_view),
]
