# IPDB ManufacturerIds to skip during ingestion.
# 0 = no manufacturer assigned, 328 = "Unknown Manufacturer" placeholder.
IPDB_SKIP_MANUFACTURER_IDS: frozenset[int] = frozenset({0, 328})

# Default paths for external data dumps (relative to backend/).
DEFAULT_IPDB_PATH = "../data/dump1/ipdb_xantari.json"
DEFAULT_OPDB_PATH = "../data/dump1/opdb_export_machines.json"
DEFAULT_OPDB_CHANGELOG_PATH = "../data/dump1/opdb_changelog.json"
DEFAULT_EXPORT_DIR = "../data/explore/pinbase_export/"
