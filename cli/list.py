from pathlib import Path
from core.config import load_config
from core.storage import load_index


def run(args):
    config = load_config(Path("config.yaml") if Path("config.yaml").exists() else None)
    base_dir = Path(config["storage"]["base_dir"])
    index = load_index(base_dir)

    if not index:
        print("No saved topics yet. Run a search first.")
        return

    print(f"{'Topic':<30} {'Papers':<10} {'Last Updated'}")
    print("-" * 60)
    for slug, info in sorted(index.items()):
        kw_str = ", ".join(info.keywords[:2])
        print(f"{info.path:<30} {info.paper_count:<10} {info.last_updated[:16]}")
