from django.shortcuts import render


def inicio(request):
    return render(request, "public/inicio.html")

def catalogo(request):
    return render (request, "public/catalogo.html")