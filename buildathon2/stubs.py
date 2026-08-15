from django.http import JsonResponse


def not_implemented(request, *args, **kwargs):
    return JsonResponse(
        {'status': 'not_implemented', 'path': request.path},
        status=501,
    )
