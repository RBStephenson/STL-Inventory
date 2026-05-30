from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:////data/stl_inventory.db"
    stl_roots: str = "/mnt/drive1,/mnt/drive2"

    # Scraper API keys (reserved for future use)
    # MMF switched to OAuth-only — scraping is used instead
    mmf_api_key: str = ""

    # Orynt3D thumbnail cache — mounted into the container from the host
    # Windows host path (example):
    #   C:\Users\<you>\AppData\Local\Packages\PlayablePrintsLimited.Orynt3D_vpht4nxhetrf0
    #   \LocalCache\Roaming\orynt3d\User Storage\Cache\orynt3dThumbnails
    orynt3d_thumbnail_cache: str = ""

    @property
    def stl_root_list(self) -> list[str]:
        return [r.strip() for r in self.stl_roots.split(",") if r.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
