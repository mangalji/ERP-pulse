"""
Project-wide DRF exception handler.
 
Wraps every error response — serializer validation errors, domain/service
exceptions, and unexpected exceptions — into the standard
{"success": false, "message": "...", "data": {}} envelope, so views never
format errors themselves and raw serializer errors are never returned
directly. Registered via REST_FRAMEWORK['EXCEPTION_HANDLER'] in
config/settings.py.
"""

import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

def standard_exception_handler(exc, context):
    """
    Convert any exception into the standard error envelope.
 
    Handling order:
    1. Exceptions DRF already understands (ValidationError,
       NotAuthenticated, PermissionDenied, NotFound, ...) — re-wrap DRF's
       own response instead of reformatting each one manually.
    2. Domain/service exceptions that declare a `status_code` attribute
       (e.g. accounts.exceptions.UserAlreadyExistsException). Apps opt in
       by setting `status_code` on their own exception classes, so
       `common` never has to import app-specific exception modules —
       this keeps common reusable for every future app, not just accounts.
    3. Anything else is unexpected: log it and return a generic 500
       without leaking internal detail to the client.
    """
    response = drf_exception_handler(exc, context)
    print(f"DEBUG_EXC_HANDLER: exception type = {type(exc).__name__}")
    print(f"DEBUG_EXC_HANDLER: exception message = {str(exc)}")
    print(f"DEBUG_EXC_HANDLER: hasattr status_code = {hasattr(exc, 'status_code')}, value = {getattr(exc, 'status_code', 'NONE')}")
    import traceback as tb_module2
    print(f"DEBUG_EXC_HANDLER: traceback:\n{''.join(tb_module2.format_exception(type(exc), exc, exc.__traceback__))}")

    if response is not None:
        print(f"DEBUG_EXC_HANDLER: drf response status = {response.status_code}")
        response.data = {
            'success': False,
            'message': _extract_message(response.data),
            'errors': response.data if response.status_code == status.HTTP_400_BAD_REQUEST else {},
            'data': {},
        }
        return response
    
    status_code = getattr(exc,'status_code',None)
    if status_code is not None:
        if status_code >= 500:
            _log_error(exc, context, status_code, level='error')
        return Response(
            {'success':False,
             'message':str(exc),
             'data':{}},
             status=status_code,
        )
    
    logger.exception('Unhandled exception is %s', context.get('view'))
    _log_error(exc, context, status.HTTP_500_INTERNAL_SERVER_ERROR, level='error')
    return Response(
        {'success':False,
         'message':'An unexpected error occurred.', 'data': {}},
         status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _log_error(exc, context, status_code, level='error'):
    """
    Persist an unhandled/server exception to monitoring.ErrorLog.

    Imported lazily (not at module top) so `common` — loaded very early
    in the app registry — never has a hard import-time dependency on the
    `monitoring` app. Failures here are swallowed: a broken monitoring
    write must never mask the original error response.
    """
    try:
        import traceback as tb_module
        from monitoring.models import ErrorLog

        request = context.get('request')
        user = getattr(request, 'user', None)

        ErrorLog.objects.create(
            level=level,
            message=str(exc),
            exception_type=type(exc).__name__,
            traceback=''.join(tb_module.format_exception(type(exc), exc, exc.__traceback__))[:10000],
            method=getattr(request, 'method', ''),
            path=getattr(request, 'path', ''),
            status_code=status_code,
            user=user if user and getattr(user, 'is_authenticated', False) else None,
        )
    except Exception:
        logger.exception('Failed to write ErrorLog entry.')

def _extract_message(error_data)->str:
    """
    Reduce DRF's (possibly nested, per-field) error data into one
    human-readable message instead of exposing the raw field/error
    structure to the client.
    """
    if isinstance(error_data,dict):
        for value in error_data.values():
            return _extract_message(value)
        return 'Invalid request.'
    if isinstance(error_data,list):
        return str(error_data[0] if error_data else 'Invalid request.')
    return str(error_data)