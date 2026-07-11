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

    if response is not None:
        if response.status_code== status.HTTP_400_BAD_REQUEST:
            response.data = {
                'success':False,
                'message': _extract_message(response.data),
                'errors':response.data,
                'data':{},
            }
        else:
            response.data={
                'success':False,
                'message':_extract_message(response.data),
                # 'message':'Validation failed.',
                'data':{},
            }
        return response
    
    status_code = getattr(exc,'status_code',None)
    if status_code is not None:
        return Response(
            {'success':False,
             'message':str(exc),
             'data':{}},
             status=status_code,
        )
    
    logger.exception('Unhandled exception is %s', context.get('view'))
    return Response(
        {'success':False,
         'message':'An unexpected error occurred.', 'data': {}},
         status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

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