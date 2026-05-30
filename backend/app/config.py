import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:////data/stl_inventory.db"
    stl_roots: str = "/mnt/drive1,/mnt/drive2"

    # Native (host) paths for the two drive mounts — used to translate
    # Docker container paths back to Windows/Mac paths for display.
    # Set these to match STL_DRIVE_1 / STL_DRIVE_2 in your .env file.
    stl_drive_1: str = ""
    stl_drive_2: str = ""

    # Scraper API keys (reserved for future use)
    # MMF switched to OAuth-only — scraping is used instead
    mmf_api_key: str = ""

    # Orynt3D thumbnail cache — mounted into the container from the host
    orynt3d_thumbnail_cache: str = ""

    @property
    def stl_root_list(self) -> list[str]:
        return [r.strip() for r in self.stl_roots.split(",") if r.strip()]

    def to_native_path(self, docker_path: str) -> str:
        """Translate a Docker container path to the native host path, if mappings are configured."""
        if self.stl_drive_1 and docker_path.startswith("/mnt/drive1"):
            suffix = docker_path[len("/mnt/drive1"):].replace("/", os.sep)
            return self.stl_drive_1.rstrip("/\\") + suffix
        if self.stl_drive_2 and docker_path.startswith("/mnt/drive2"):
            suffix = docker_path[len("/mnt/drive2"):].replace("/", os.sep)
            return self.stl_drive_2.rstrip("/\\") + suffix
        return docker_path

    class Config:
        env_file = ".env"


settings = Settings()
