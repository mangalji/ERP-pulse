"""
Logging configuration for AGSuite ERP.

Console logging is used in all environments.
Production platforms (Render, Railway, etc.) automatically capture stdout.
"""

from decouple import config


LOG_LEVEL = config(
    "LOG_LEVEL",
    default="INFO",
)


LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {

        "simple": {

            "format": "[{asctime}] {levelname} {name}: {message}",

            "style": "{",
        },

    },

    "handlers": {

        "console": {

            "class": "logging.StreamHandler",

            "formatter": "simple",

        },

    },

    "root": {

        "handlers": ["console"],

        "level": LOG_LEVEL,

    },

    "loggers": {

        "django.request": {

            "handlers": ["console"],

            "level": "ERROR",

            "propagate": False,

        },

        "django.db.backends": {

            "handlers": ["console"],

            "level": config(
                "DJANGO_DB_LOG_LEVEL",
                default="WARNING",
            ),

            "propagate": False,

        },

        "django.security": {

            "handlers": ["console"],

            "level": "WARNING",

            "propagate": False,

        },

        "monitoring": {

            "handlers": ["console"],

            "level": config(
                "MONITORING_LOG_LEVEL",
                default="INFO",
            ),

            "propagate": False,

        },

        # Stage timings are useful during focused profiling but are too noisy
        # for normal terminal/application logs. Keep errors from other
        # loggers visible while suppressing routine INFO timing events.
        "performance": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },

    },

}
