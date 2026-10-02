import sys
from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=lambda v: [s.strip() for s in v.split(",")])

# CSRF Trusted Origins for cross-origin requests
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_apscheduler",
    "corsheaders",
    "lpr_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lpr_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lpr_project.wsgi.application"

# Database
# Use environment variable for database location, fallback to project root
DATABASE_PATH = config("DATABASE_PATH", default=str(BASE_DIR / "db.sqlite3"), cast=str)
DATABASE_DIR = Path(DATABASE_PATH).parent
LOG_DIR = DATABASE_DIR

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "lpr_app" / "static",
]

# Media files (Uploaded images)
MEDIA_URL = "/media/"
# Use environment variable for media location, fallback to project root
MEDIA_ROOT = str(config("MEDIA_PATH", default=str(BASE_DIR / "media"), cast=str))

# Prometheus metrics state, persisted between restarts. Defaults to a location
# derived from the data directory so local runs work without extra configuration.
METRICS_FILE_PATH = config("METRICS_FILE_PATH", default=str(LOG_DIR / "metrics_state.json"), cast=str)

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 250 * 1024  # 250KB
DATA_UPLOAD_MAX_MEMORY_SIZE = 250 * 1024  # 250KB
UPLOAD_FILE_MAX_SIZE = config("UPLOAD_FILE_MAX_SIZE", default=1048576, cast=int)

# Allowed file types for upload
ALLOWED_IMAGE_TYPES = ["jpeg", "jpg", "png", "webp"]

# Detection pipeline settings
MIN_PLATE_HEIGHT = config("MIN_PLATE_HEIGHT", default=30, cast=int)
PLATE_HEIGHT_FRACTION = config("PLATE_HEIGHT_FRACTION", default=0.05, cast=float)

# Detection validation thresholds (filter false positives)
DETECTION_MIN_CONFIDENCE = config("DETECTION_MIN_CONFIDENCE", default=0.5, cast=float)
DETECTION_MIN_BOX_AREA_FRACTION = config("DETECTION_MIN_BOX_AREA_FRACTION", default=0.001, cast=float)
DETECTION_MAX_BOX_AREA_FRACTION = config("DETECTION_MAX_BOX_AREA_FRACTION", default=0.5, cast=float)
DETECTION_MIN_PLATE_ASPECT = config("DETECTION_MIN_PLATE_ASPECT", default=1.5, cast=float)
DETECTION_MAX_PLATE_ASPECT = config("DETECTION_MAX_PLATE_ASPECT", default=10.0, cast=float)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)
CORS_ALLOW_PRIVATE_NETWORK = config("CORS_ALLOW_PRIVATE_NETWORK", default=False, cast=bool)

RATE_LIMIT_ENABLE = config("RATE_LIMIT_ENABLE", default=True, cast=bool)
RATE_LIMIT_RATE = config("RATE_LIMIT_RATE", default="2/min", cast=str)
RATE_LIMIT_EXCLUDE_PATHS = config(
    "RATE_LIMIT_EXCLUDE_PATHS",
    default="/health/,/api/v1/health-light/",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)
RATE_LIMIT_INCLUDE_PATHS = config(
    "RATE_LIMIT_INCLUDE_PATHS",
    default="/api/v1/ocr/",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

if "test" in sys.argv:
    RATE_LIMIT_ENABLE = False

MIDDLEWARE.append("lpr_app.middleware.rate_limit.RateLimitMiddleware")

OCR_CROP_PADDING_PX = config("OCR_CROP_PADDING_PX", default=25, cast=int)

# ==========================================================================
# Local ONNX pipeline backend
# ==========================================================================
# Which backend processes images: "llm" (the Qwen3-VL path) or "local" (the ONNX
# detector + recognizer). The default is "local" because it is the only path that
# fits the sub-500ms latency budget: 60ms mean per image against the LLM's 3600ms.
#
# The tradeoff, stated plainly: the local backend's *text accuracy is unmeasured*.
# The corpus annotates plate boxes with no transcription labels, so the recorded
# comparison can show it reads more plates than the LLM (0.95 vs 0.375) but cannot
# show that those reads are correct -- it also misreads some plates it finds
# (QG.260 -> 0G260). Higher coverage is not higher accuracy.
# See openspec/changes/measure-local-backend-accuracy/COMPARISON.md.
#
# Rolling back is one configuration change: set PIPELINE_BACKEND=llm and redeploy.
# No migration, no data rewrite, and the LLM path remains fully tested.
PIPELINE_BACKEND = config("PIPELINE_BACKEND", default="local", cast=str)

# Artifacts are resolved relative to this directory. It is outside MEDIA_ROOT so
# uploads cannot overwrite a model, and it is gitignored.
PIPELINE_MODEL_DIR = config("PIPELINE_MODEL_DIR", default=str(BASE_DIR / "model" / "plate"), cast=str)

PIPELINE_DETECTOR_MODEL = config("PIPELINE_DETECTOR_MODEL", default="plate_yolox_tiny_640.onnx", cast=str)
# Detector input resolution is recall-critical, not a speed knob: the corpus
# median plate height is 61px with a 36px 10th percentile, and a resolution too
# low to resolve those plates loses them outright.
PIPELINE_DETECTOR_INPUT_SIZE = config(
    "PIPELINE_DETECTOR_INPUT_SIZE",
    default="640,640",
    cast=lambda v: tuple(int(part) for part in v.split(",")),
)
PIPELINE_DETECTOR_CONF_THRESHOLD = config("PIPELINE_DETECTOR_CONF_THRESHOLD", default=0.3, cast=float)
PIPELINE_DETECTOR_NMS_IOU = config("PIPELINE_DETECTOR_NMS_IOU", default=0.45, cast=float)

# Plate layouts: "stacked" (two rows) or "single_line". Decided from the
# detection's aspect ratio against this threshold, not configured per region.
PIPELINE_LAYOUT_THRESHOLD = config("PIPELINE_LAYOUT_THRESHOLD", default=2.0, cast=float)

PIPELINE_OCR_MODEL = config("PIPELINE_OCR_MODEL", default="plate_ocr_ppocrv5_mobile.onnx", cast=str)
PIPELINE_OCR_DICT = config("PIPELINE_OCR_DICT", default="plate_ocr_dict.json", cast=str)
# Crops per recognizer invocation. One plate is one crop unless it is stacked
# and splitting is enabled.
PIPELINE_OCR_BATCH_SIZE = config("PIPELINE_OCR_BATCH_SIZE", default=8, cast=int)
PIPELINE_OCR_CHARSET_PROFILE = config("PIPELINE_OCR_CHARSET_PROFILE", default="alphanumeric", cast=str)
# Off by default: on this corpus, splitting reads captions as a second line more
# often than it rescues genuinely stacked plates. See the OCR stage docstring.
PIPELINE_OCR_SPLIT_STACKED = config("PIPELINE_OCR_SPLIT_STACKED", default=False, cast=bool)

# When rectification is enabled the perspective transform establishes the crop
# boundary, so OCR_CROP_PADDING_PX is not applied. When disabled, padding is.
PIPELINE_RECTIFY_ENABLED = config("PIPELINE_RECTIFY_ENABLED", default=True, cast=bool)

# cpu | cuda | rocm. An unavailable provider falls back to CPU with a warning; the
# supported deployment target is CPU, and ROCm is never a prerequisite.
PIPELINE_PROVIDER = config("PIPELINE_PROVIDER", default="cpu", cast=str)

# Latency budgets in seconds. The end-to-end budget is the project's
# sub-500ms target; stage budgets are per stage name and are optional.
PIPELINE_LATENCY_BUDGET_SECONDS = config("PIPELINE_LATENCY_BUDGET_SECONDS", default=0.5, cast=float)


def _parse_stage_budgets(value: str) -> dict[str, float]:
    """Parse ``stage=seconds`` pairs, e.g. ``detect_plate=0.4,read_plate=0.1``.

    An entry without ``=``, or with a non-numeric duration, is ignored rather than
    fatal: a malformed budget should not stop the application from starting, and a
    stage with no parsed budget is the same as one with no budget at all.
    """
    budgets: dict[str, float] = {}
    for entry in value.split(","):
        name, separator, seconds = entry.partition("=")
        name = name.strip()
        if not separator or not name:
            continue
        try:
            budgets[name] = float(seconds)
        except ValueError:
            continue
    return budgets


PIPELINE_STAGE_BUDGETS = config("PIPELINE_STAGE_BUDGETS", default="", cast=_parse_stage_budgets)

PROCESSING_TIMEOUT_MINUTES = config("PROCESSING_TIMEOUT_MINUTES", default=5, cast=int)
MAX_RETRIES = config("MAX_RETRIES", default=2, cast=int)
RETRY_BATCH_SIZE = config("RETRY_BATCH_SIZE", default=5, cast=int)
RETRY_INTERVAL_MINUTES = config("RETRY_INTERVAL_MINUTES", default=5, cast=int)
RETRY_SCHEDULER_ENABLED = config("RETRY_SCHEDULER_ENABLED", default=True, cast=bool)

# Background refresh interval for the cached availability series.
# Keep well below the Prometheus scrape interval so served data is never
# more than one scrape interval stale.
AVAILABILITY_REFRESH_SECONDS = config("AVAILABILITY_REFRESH_SECONDS", default=60, cast=int)

# Qwen3-VL API Configuration
QWEN_API_KEY = config("QWEN_API_KEY", default="")
QWEN_BASE_URL = config("QWEN_BASE_URL", default="https://ollama.computedsynergy.com/v1")
QWEN_MODEL = config("QWEN_MODEL", default="qwen3-vl-4b-instruct")

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Security settings
X_FRAME_OPTIONS = "DENY"

# Email settings (for error notifications, optional)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Logging configuration

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "lpr_app": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
# Canary Configuration
CANARY_ENABLED = config("CANARY_ENABLED", default="true", cast=bool)
CANARY_HEADER_NAME = config("CANARY_HEADER_NAME", default="X-Canary-Request")
CANARY_HEADER_VALUE = config("CANARY_HEADER_VALUE", default="random-string-not-known-outside")
CANARY_INTERVAL = config("CANARY_INTERVAL", default="900", cast=int)

PROMETHEUS_URL = config("PROMETHEUS_URL", default="http://prometheus:9090")
