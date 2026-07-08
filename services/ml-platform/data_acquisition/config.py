import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DataAcquisitionConfig:
    base_dir: str = "./datasets"
    max_retries: int = 3
    retry_delay: float = 5.0
    chunk_size: int = 8192
    verify_checksums: bool = True
    preserve_archives: bool = False
    log_level: str = "INFO"

    @property
    def raw_dir(self) -> str:
        return f"{self.base_dir}/raw"

    @property
    def processed_dir(self) -> str:
        return f"{self.base_dir}/processed"

    @property
    def normalized_dir(self) -> str:
        return f"{self.base_dir}/normalized"

    @property
    def features_dir(self) -> str:
        return f"{self.base_dir}/features"

    @property
    def training_dir(self) -> str:
        return f"{self.base_dir}/training"

    @property
    def registry_dir(self) -> str:
        return f"{self.base_dir}/registry"


def get_config() -> DataAcquisitionConfig:
    return DataAcquisitionConfig(
        base_dir=os.getenv("DATASET_DIR", "./datasets"),
        max_retries=int(os.getenv("DA_MAX_RETRIES", "3")),
        retry_delay=float(os.getenv("DA_RETRY_DELAY", "5.0")),
        chunk_size=int(os.getenv("DA_CHUNK_SIZE", "8192")),
        verify_checksums=os.getenv("DA_VERIFY_CHECKSUMS", "1") == "1",
        preserve_archives=os.getenv("DA_PRESERVE_ARCHIVES", "0") == "1",
        log_level=os.getenv("DA_LOG_LEVEL", "INFO"),
    )
