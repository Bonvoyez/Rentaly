import os
from pathlib import Path
from uuid import UUID

IMAGE_DIR = Path(os.environ.get("IMAGE_DIR", "/app/storage/images"))


def save_image(inspection_id: UUID, data: bytes) -> str:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{inspection_id}.jpg"
    path = IMAGE_DIR / filename
    tmp = path.with_name(filename + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return str(path)
