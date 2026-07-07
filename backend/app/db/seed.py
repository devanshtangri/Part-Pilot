from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import PartType


BUILTIN_PART_TYPES = [
    "Resistor",
    "Potentiometer",
    "Capacitor",
    "Inductor",
    "Diode",
    "Zener Diode",
    "Schottky Diode",
    "LED",
    "RGB LED",
    "Optocoupler",
    "NPN Transistor",
    "PNP Transistor",
    "MOSFET",
    "Voltage Regulator",
    "IC",
    "Microcontroller",
    "Relay",
    "Motor",
    "Servo Motor",
    "Stepper Motor",
    "Solenoid",
    "Buzzer",
    "Speaker",
    "Push Button",
    "Switch",
    "Rotary Encoder",
    "Connector",
    "Pin Header",
    "Terminal Block",
    "Fuse",
    "Mechanical Hardware",
    "Module",
    "Sensor",
    "Custom",
]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def seed_builtin_part_types(db: Session) -> int:
    created = 0
    existing_slugs = {
        row.slug
        for row in db.query(PartType.slug).filter(PartType.is_builtin.is_(True)).all()
    }

    for name in BUILTIN_PART_TYPES:
        slug = slugify(name)
        if slug in existing_slugs:
            continue

        db.add(
            PartType(
                name=name,
                slug=slug,
                is_builtin=True,
                is_active=True,
                template_version=1,
            )
        )
        created += 1

    db.commit()
    return created


def main() -> None:
    db = SessionLocal()
    try:
        created = seed_builtin_part_types(db)
        print(f"Seeded built-in part types. Created: {created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
