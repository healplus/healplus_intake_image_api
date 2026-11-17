"""Limites e verificações determinísticas dos bytes da fotografia recebida."""

import io
import warnings

from PIL import Image, ImageCms, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
MAX_IMAGE_DIMENSION = 8192
MAX_BASE64_LENGTH = 4 * ((MAX_IMAGE_BYTES + 2) // 3)

# Campos EXIF que podem identificar o paciente, o profissional ou o aparelho.
SENSITIVE_EXIF_TAGS = {34853, 315, 37500, 42032, 42033, 42037}


def _validate_color_profile(profile_bytes: bytes | None) -> None:
    """Confere um ICC real e sua equivalência prática ao espaço sRGB."""
    if not profile_bytes:
        raise ValueError("Media.content.data requer perfil ICC sRGB incorporado")
    try:
        if len(profile_bytes) > 1024 * 1024:
            raise ValueError("Perfil ICC excede 1 MiB")
        profile = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
        if profile.profile.xcolor_space.strip() != "RGB":
            raise ValueError("O perfil ICC deve usar o espaço RGB")
        # O nome do perfil não basta: verifica também a transformação de uma
        # amostra de cores, impedindo um perfil de outro espaço renomeado sRGB.
        if "srgb" not in ImageCms.getProfileDescription(profile).lower():
            raise ValueError("O perfil ICC deve descrever o espaço sRGB")
        colors = [
            (red, green, blue)
            for red in (0, 64, 128, 192, 255)
            for green in (0, 64, 128, 192, 255)
            for blue in (0, 64, 128, 192, 255)
        ]
        sample = Image.new("RGB", (len(colors), 1))
        sample.putdata(colors)
        converted = ImageCms.profileToProfile(
            sample, profile, ImageCms.createProfile("sRGB"), outputMode="RGB"
        )
        if any(
            abs(source - target) > 3
            for index, original in enumerate(colors)
            for corrected in (converted.getpixel((index, 0)),)
            for source, target in zip(original, corrected)
        ):
            raise ValueError("O perfil ICC não corresponde ao espaço sRGB")
    except (OSError, TypeError, ValueError, ImageCms.PyCMSError) as error:
        raise ValueError(f"Media.content.data contém perfil ICC inválido: {error}") from error


def inspect_jpeg(data: bytes) -> tuple[int, int]:
    """Decodifica o JPEG e rejeita truncamento, excesso e metadados sensíveis.

    Os pixels não são alterados ou recomprimidos; size e hash continuam
    identificando exatamente o arquivo submetido pelo cliente.
    """
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Media.content.data deve ter no máximo 10 MiB")
    if not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        raise ValueError("Media.content.data deve conter um JPEG completo")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
                width, height = image.size
                if (
                    width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ValueError("JPEG excede 8192 pixels por lado ou 24 megapixels")
                if image.mode != "RGB":
                    raise ValueError("O JPEG deve conter pixels RGB em sRGB")
                exif = image.getexif()
                if exif.get(274, 1) != 1:
                    raise ValueError("A orientação EXIF deve ser 1; normalize os pixels no app")
                nested_exif = exif.get_ifd(34665) if 34665 in exif else {}
                if SENSITIVE_EXIF_TAGS.intersection(exif) or SENSITIVE_EXIF_TAGS.intersection(nested_exif):
                    raise ValueError("Remova GPS, proprietário e números de série do EXIF")
                _validate_color_profile(image.info.get("icc_profile"))
                image.load()
                return width, height
    except ValueError:
        raise
    except (
        OSError,
        SyntaxError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("Media.content.data não é um JPEG íntegro e decodificável") from error
