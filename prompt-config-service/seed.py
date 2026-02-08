"""Load initial seed data from YAML if the database is empty."""

import logging
import uuid
from pathlib import Path
from datetime import datetime

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.placeholder import Placeholder, PlaceholderValue
from models.profile import Profile, ProfilePlaceholderSetting

logger = logging.getLogger(__name__)


def _load_yaml() -> dict:
    """Load seed data from initial_data.yaml."""
    base = Path(__file__).resolve().parent
    yaml_path = base / "initial_data.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Seed data file not found: {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def load_seed_if_empty(session: AsyncSession) -> bool:
    """
    If placeholders table is empty, load placeholders, values, profiles and profile settings from initial_data.yaml.
    Returns True if seed was loaded, False if DB already had data.
    """
    result = await session.execute(select(Placeholder).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Seed already present, skipping initial data load")
        return False

    data = _load_yaml()
    now = datetime.utcnow()
    placeholder_ids: dict[str, uuid.UUID] = {}
    placeholder_value_by_name: dict[str, dict[str, uuid.UUID]] = {}
    placeholder_value_by_key: dict[str, uuid.UUID] = {}
    profile_ids: dict[str, uuid.UUID] = {}

    # Create placeholders
    placeholders: list[Placeholder] = []
    for p in data["placeholders"]:
        pid = uuid.uuid4()
        placeholder_ids[p["name"]] = pid
        placeholder_value_by_name[p["name"]] = {}
        placeholders.append(
            Placeholder(
                id=pid,
                name=p["name"],
                display_name=p["display_name"],
                description=p.get("description"),
                created_at=now,
                updated_at=now,
            )
        )
    session.add_all(placeholders)
    await session.flush()

    # Create placeholder values
    values: list[PlaceholderValue] = []
    for p in data["placeholders"]:
        pid = placeholder_ids[p["name"]]
        for v in p["values"]:
            vid = uuid.uuid4()
            value_name = v.get("name", v["value"])
            placeholder_value_by_name[p["name"]][value_name] = vid
            placeholder_value_by_key[f"{p['name']}:{v['value']}"] = vid
            values.append(
                PlaceholderValue(
                    id=vid,
                    placeholder_id=pid,
                    name=value_name[:100] if isinstance(value_name, str) else str(value_name)[:100],
                    value=v["value"],
                    display_name=v["display_name"],
                    description=v.get("description"),
                    created_at=now,
                )
            )
    session.add_all(values)
    await session.flush()

    # Create profiles
    profiles_list: list[Profile] = []
    for pr in data.get("profiles", []):
        prid = uuid.uuid4()
        profile_ids[pr["name"]] = prid
        profiles_list.append(
            Profile(
                id=prid,
                name=pr["name"],
                display_name=pr["display_name"],
                category=pr["category"],
                description=pr.get("description"),
                created_at=now,
                updated_at=now,
            )
        )
    session.add_all(profiles_list)
    await session.flush()

    # Create profile_placeholder_settings
    settings_list: list[ProfilePlaceholderSetting] = []
    for pr in data.get("profiles", []):
        prid = profile_ids[pr["name"]]
        for placeholder_name, value_ref in pr.get("settings", {}).items():
            if placeholder_name not in placeholder_ids:
                logger.warning("Placeholder %s not found for profile %s", placeholder_name, pr["name"])
                continue
            pid = placeholder_ids[placeholder_name]
            value_id = None
            if placeholder_name in placeholder_value_by_name and value_ref in placeholder_value_by_name[placeholder_name]:
                value_id = placeholder_value_by_name[placeholder_name][value_ref]
            else:
                value_key = f"{placeholder_name}:{value_ref}"
                value_id = placeholder_value_by_key.get(value_key)
            if not value_id:
                logger.warning("Value %s not found for placeholder %s", value_ref, placeholder_name)
                continue
            settings_list.append(
                ProfilePlaceholderSetting(
                    profile_id=prid,
                    placeholder_id=pid,
                    placeholder_value_id=value_id,
                    created_at=now,
                )
            )
    session.add_all(settings_list)
    await session.commit()
    logger.info(
        "Seed loaded: %s placeholders, %s values, %s profiles, %s profile settings",
        len(placeholders),
        len(values),
        len(profiles_list),
        len(settings_list),
    )
    return True
