# from django.contrib.auth.hashers import make_password, check_password

# def hash_password(password:str) -> str:

#     """
#     args: plain text value
#     return: hashed value
#     """

#     return make_password(password)

# def verify_hash(value:str,hashed_value:str)->bool:

#     """
#     verify hash value

#     args: 
#         value: plain text value
#         hashed_value: hashed value
    
#     return: True if valid.
#     """

#     return check_password(value,hashed_value)



from django.contrib.auth.hashers import check_password, make_password


def hash_value(raw_value: str) -> str:
    """
    Hash a raw string using Django's configured password hasher.

    Reused for OTP codes (not just passwords) per AUTHENTICATION_DESIGN.md
    Decision AUTH-007: OTP codes are hashed at rest using the same
    precedent as passwords, rather than a separate hashing scheme.
    """
    return make_password(raw_value)


def verify_value(raw_value: str, hashed_value: str) -> bool:
    """Check whether a raw string matches a previously hashed value."""
    return check_password(raw_value, hashed_value)
