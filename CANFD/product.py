from dataclasses import dataclass


@dataclass(frozen=True)
class ProductInfo:
    internal_name: str
    display_name: str
    version: str
    organization: str
    config_profile_env: str
    log_dir_env: str


PRODUCT_INFO = ProductInfo(
    internal_name="DCBMS",
    display_name="DCBMS CANFD Host",
    version="2.0.0",
    organization="AIDC",
    config_profile_env="DCBMS_PROFILE",
    log_dir_env="DCBMS_LOG_DIR",
)
