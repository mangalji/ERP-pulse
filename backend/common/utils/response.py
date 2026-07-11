
"""
Standard API response builder.
 
Every successful response across the project must follow the standard
envelope defined in BACKEND_CONTEXT.md / CODE_STYLE.md:
    {"success": true, "message": "...", "data": {...}}
 
Error responses follow the same envelope via
common/exception_handler.py — views never build error bodies by hand.
"""
from rest_framework.response import Response

def success_response(*,message:str,data:dict|None=None, status_code:int=200)->Response:
    """Build a success envelope response"""
    return Response(
        {"success":True,
         'message':message,
         'data':data if data is not None else {}},
         status=status_code,
    )