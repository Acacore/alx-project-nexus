from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from .serializers import *
# Create your views here.
def home(request):
    return HttpResponse("<h1>Hello, World <br> Wellcome to Mercarol</h1>")
