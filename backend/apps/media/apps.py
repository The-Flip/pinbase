import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    verbose_name = "Media"

    def ready(self):
        _register_heif()
        _check_avif()


def _register_heif():
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        logger.warning("HEIF support unavailable; HEIC uploads will fail.")


def _check_avif():
    from PIL import Image

    if "AVIF" not in Image.SAVE:
        logger.warning("AVIF codec unavailable; AVIF uploads will fail.")
