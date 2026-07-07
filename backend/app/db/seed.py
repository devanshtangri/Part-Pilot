from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AppSetting, PartType, PartTypeField


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


DEFAULT_APP_SETTINGS: dict[str, dict[str, object]] = {
    "setup.completed": {"value_json": False, "value_text": None},
    "app.display_name": {"value_json": "Part Pilot", "value_text": "Part Pilot"},
    "appearance.theme": {"value_json": "dark", "value_text": "dark"},
    "appearance.light_theme_available": {"value_json": True, "value_text": None},
    "currency.default": {"value_json": None, "value_text": None},
    "timezone.default": {"value_json": None, "value_text": None},
    "search.show_out_of_stock_section": {"value_json": True, "value_text": None},
    "price.warn_when_missing": {"value_json": True, "value_text": None},
    "reservations.expiry.mode": {"value_json": "none", "value_text": "none"},
    "reservations.expiry.default_days": {"value_json": None, "value_text": None},
    "backups.enabled": {"value_json": True, "value_text": None},
    "backups.frequency": {"value_json": "daily", "value_text": "daily"},
    "backups.path": {"value_json": "/data/backups", "value_text": "/data/backups"},
    "backups.retention_count": {"value_json": 14, "value_text": None},
    "mcp.enabled": {"value_json": False, "value_text": None},
    "mcp.read_tools_enabled": {"value_json": True, "value_text": None},
    "mcp.write_tools_enabled": {"value_json": False, "value_text": None},
}


def field(
    key: str,
    label: str,
    field_type: str,
    *,
    required: bool = False,
    unit: str | None = None,
    options: list[str] | dict[str, Any] | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    return {
        "field_key": key,
        "label": label,
        "field_type": field_type,
        "is_required": required,
        "default_unit": unit,
        "options_json": options,
        "help_text": help_text,
    }


BUILTIN_TEMPLATE_FIELDS: dict[str, list[dict[str, Any]]] = {
    "Resistor": [
        field("resistance", "Resistance", "unit_value", unit="Ω"),
        field("tolerance", "Tolerance", "unit_value", unit="%"),
        field("power_rating", "Power rating", "unit_value", unit="W"),
        field("package", "Package / size", "text"),
        field("temperature_coefficient", "Temperature coefficient", "unit_value", unit="ppm/°C"),
    ],
    "Potentiometer": [
        field("resistance", "Resistance", "unit_value", unit="Ω"),
        field("taper", "Taper", "dropdown", options=["Linear", "Logarithmic", "Audio", "Other"]),
        field("power_rating", "Power rating", "unit_value", unit="W"),
        field("mounting_type", "Mounting type", "dropdown", options=["Panel", "PCB", "Trimmer", "Other"]),
        field("package", "Package / size", "text"),
    ],
    "Capacitor": [
        field("capacitance", "Capacitance", "unit_value", unit="uF"),
        field("voltage_rating", "Voltage rating", "unit_value", unit="V"),
        field("tolerance", "Tolerance", "unit_value", unit="%"),
        field("capacitor_type", "Capacitor type", "dropdown", options=["Ceramic", "Electrolytic", "Tantalum", "Film", "Supercapacitor", "Other"]),
        field("package", "Package / size", "text"),
        field("polarity", "Polarized", "boolean"),
    ],
    "Inductor": [
        field("inductance", "Inductance", "unit_value", unit="uH"),
        field("current_rating", "Current rating", "unit_value", unit="A"),
        field("dc_resistance", "DC resistance", "unit_value", unit="Ω"),
        field("package", "Package / size", "text"),
    ],
    "Diode": [
        field("forward_voltage", "Forward voltage", "unit_value", unit="V"),
        field("max_current", "Maximum current", "unit_value", unit="A"),
        field("reverse_voltage", "Reverse voltage", "unit_value", unit="V"),
        field("package", "Package", "text"),
    ],
    "Zener Diode": [
        field("zener_voltage", "Zener voltage", "unit_value", unit="V"),
        field("power_rating", "Power rating", "unit_value", unit="W"),
        field("tolerance", "Tolerance", "unit_value", unit="%"),
        field("package", "Package", "text"),
    ],
    "Schottky Diode": [
        field("forward_voltage", "Forward voltage", "unit_value", unit="V"),
        field("max_current", "Maximum current", "unit_value", unit="A"),
        field("reverse_voltage", "Reverse voltage", "unit_value", unit="V"),
        field("package", "Package", "text"),
    ],
    "LED": [
        field("color", "Color", "dropdown", options=["Red", "Green", "Blue", "White", "Warm White", "Yellow", "Orange", "RGB", "Other"]),
        field("forward_voltage", "Forward voltage", "unit_value", unit="V"),
        field("forward_current", "Forward current", "unit_value", unit="mA"),
        field("size", "Size", "text"),
        field("lens_type", "Lens type", "dropdown", options=["Clear", "Diffused", "Water clear", "Other"]),
    ],
    "RGB LED": [
        field("led_type", "RGB LED type", "dropdown", options=["Common Anode", "Common Cathode", "Addressable", "Other"]),
        field("package", "Package / size", "text"),
        field("forward_voltage_red", "Red forward voltage", "unit_value", unit="V"),
        field("forward_voltage_green", "Green forward voltage", "unit_value", unit="V"),
        field("forward_voltage_blue", "Blue forward voltage", "unit_value", unit="V"),
    ],
    "Optocoupler": [
        field("channels", "Channels", "number"),
        field("input_forward_voltage", "Input forward voltage", "unit_value", unit="V"),
        field("output_type", "Output type", "dropdown", options=["Phototransistor", "Triac", "Logic", "MOSFET", "Other"]),
        field("isolation_voltage", "Isolation voltage", "unit_value", unit="V"),
        field("package", "Package", "text"),
    ],
    "NPN Transistor": [
        field("max_voltage", "Maximum voltage", "unit_value", unit="V"),
        field("max_current", "Maximum current", "unit_value", unit="A"),
        field("gain_hfe", "Gain / hFE", "number"),
        field("package", "Package", "text"),
    ],
    "PNP Transistor": [
        field("max_voltage", "Maximum voltage", "unit_value", unit="V"),
        field("max_current", "Maximum current", "unit_value", unit="A"),
        field("gain_hfe", "Gain / hFE", "number"),
        field("package", "Package", "text"),
    ],
    "MOSFET": [
        field("channel_type", "Channel type", "dropdown", options=["N-channel", "P-channel"]),
        field("max_voltage", "Maximum voltage", "unit_value", unit="V"),
        field("max_current", "Maximum current", "unit_value", unit="A"),
        field("rds_on", "RDS(on)", "unit_value", unit="Ω"),
        field("gate_threshold_voltage", "Gate threshold voltage", "unit_value", unit="V"),
        field("logic_level", "Logic-level gate", "boolean"),
        field("package", "Package", "text"),
    ],
    "Voltage Regulator": [
        field("regulator_type", "Regulator type", "dropdown", options=["Linear", "Buck", "Boost", "Buck-Boost", "LDO", "Other"]),
        field("output_voltage", "Output voltage", "unit_value", unit="V"),
        field("max_current", "Maximum current", "unit_value", unit="A"),
        field("input_voltage_range", "Input voltage range", "text"),
        field("package", "Package", "text"),
    ],
    "IC": [
        field("function", "Function", "text"),
        field("package", "Package", "text"),
        field("pin_count", "Pin count", "number"),
        field("supply_voltage", "Supply voltage", "text"),
        field("interface", "Interface", "text"),
    ],
    "Microcontroller": [
        field("architecture", "Architecture", "text"),
        field("flash", "Flash", "unit_value", unit="KB"),
        field("ram", "RAM", "unit_value", unit="KB"),
        field("gpio_count", "GPIO count", "number"),
        field("supply_voltage", "Supply voltage", "text"),
        field("package", "Package / board", "text"),
    ],
    "Relay": [
        field("coil_voltage", "Coil voltage", "unit_value", unit="V"),
        field("contact_rating", "Contact rating", "text"),
        field("contact_form", "Contact form", "dropdown", options=["SPST", "SPDT", "DPST", "DPDT", "Other"]),
        field("mounting_type", "Mounting type", "dropdown", options=["PCB", "Panel", "DIN rail", "Other"]),
    ],
    "Motor": [
        field("motor_type", "Motor type", "dropdown", options=["DC", "BLDC", "AC", "Gear motor", "Other"]),
        field("voltage", "Voltage", "unit_value", unit="V"),
        field("current", "Current", "unit_value", unit="A"),
        field("rpm", "RPM", "number"),
        field("shaft_size", "Shaft size", "unit_value", unit="mm"),
    ],
    "Servo Motor": [
        field("voltage", "Voltage", "unit_value", unit="V"),
        field("torque", "Torque", "text"),
        field("rotation_range", "Rotation range", "text"),
        field("gear_type", "Gear type", "dropdown", options=["Plastic", "Metal", "Other"]),
    ],
    "Stepper Motor": [
        field("step_angle", "Step angle", "unit_value", unit="°"),
        field("rated_voltage", "Rated voltage", "unit_value", unit="V"),
        field("rated_current", "Rated current", "unit_value", unit="A"),
        field("phase_count", "Phase count", "number"),
        field("shaft_size", "Shaft size", "unit_value", unit="mm"),
    ],
    "Solenoid": [
        field("voltage", "Voltage", "unit_value", unit="V"),
        field("current", "Current", "unit_value", unit="A"),
        field("stroke_length", "Stroke length", "unit_value", unit="mm"),
        field("type", "Type", "dropdown", options=["Push", "Pull", "Push-Pull", "Valve", "Other"]),
    ],
    "Buzzer": [
        field("buzzer_type", "Buzzer type", "dropdown", options=["Active", "Passive", "Piezo", "Magnetic", "Other"]),
        field("voltage", "Voltage", "unit_value", unit="V"),
        field("frequency", "Frequency", "unit_value", unit="Hz"),
        field("mounting_type", "Mounting type", "text"),
    ],
    "Speaker": [
        field("impedance", "Impedance", "unit_value", unit="Ω"),
        field("power_rating", "Power rating", "unit_value", unit="W"),
        field("diameter", "Diameter", "unit_value", unit="mm"),
        field("connector_type", "Connector type", "text"),
    ],
    "Push Button": [
        field("button_type", "Button type", "dropdown", options=["Momentary", "Latching", "Tactile", "Other"]),
        field("contact_type", "Contact type", "dropdown", options=["NO", "NC", "NO+NC", "Other"]),
        field("mounting_type", "Mounting type", "dropdown", options=["PCB", "Panel", "Breadboard", "Other"]),
        field("cap_color", "Cap color", "text"),
    ],
    "Switch": [
        field("switch_type", "Switch type", "dropdown", options=["Toggle", "Slide", "Rocker", "DIP", "Limit", "Other"]),
        field("contact_form", "Contact form", "dropdown", options=["SPST", "SPDT", "DPST", "DPDT", "Other"]),
        field("current_rating", "Current rating", "unit_value", unit="A"),
        field("voltage_rating", "Voltage rating", "unit_value", unit="V"),
    ],
    "Rotary Encoder": [
        field("encoder_type", "Encoder type", "dropdown", options=["Incremental", "Absolute", "Other"]),
        field("pulses_per_revolution", "Pulses per revolution", "number"),
        field("has_push_button", "Has push button", "boolean"),
        field("mounting_type", "Mounting type", "text"),
    ],
    "Connector": [
        field("connector_type", "Connector type", "text"),
        field("pin_count", "Pin count", "number"),
        field("pitch", "Pitch", "unit_value", unit="mm"),
        field("gender", "Gender", "dropdown", options=["Male", "Female", "Other"]),
        field("mounting_type", "Mounting type", "dropdown", options=["Through-hole", "SMD", "Panel", "Cable", "Other"]),
    ],
    "Pin Header": [
        field("pin_count", "Pin count", "number"),
        field("rows", "Rows", "number"),
        field("pitch", "Pitch", "unit_value", unit="mm"),
        field("gender", "Gender", "dropdown", options=["Male", "Female"]),
        field("angle", "Angle", "dropdown", options=["Straight", "Right-angle"]),
    ],
    "Terminal Block": [
        field("positions", "Positions", "number"),
        field("pitch", "Pitch", "unit_value", unit="mm"),
        field("current_rating", "Current rating", "unit_value", unit="A"),
        field("wire_size", "Wire size", "text"),
    ],
    "Fuse": [
        field("current_rating", "Current rating", "unit_value", unit="A"),
        field("voltage_rating", "Voltage rating", "unit_value", unit="V"),
        field("fuse_type", "Fuse type", "dropdown", options=["Fast-blow", "Slow-blow", "Resettable", "Other"]),
        field("package", "Package / size", "text"),
    ],
    "Mechanical Hardware": [
        field("size", "Size", "text"),
        field("length", "Length", "unit_value", unit="mm"),
        field("thread_type", "Thread type", "text"),
        field("material", "Material", "text"),
        field("head_type", "Head type", "text"),
    ],
    "Module": [
        field("module_function", "Module function", "text"),
        field("input_voltage", "Input voltage", "text"),
        field("output_voltage", "Output voltage", "text"),
        field("interface", "Interface", "text"),
        field("board_size", "Board size", "text"),
    ],
    "Sensor": [
        field("sensor_type", "Sensor type", "text"),
        field("measured_quantity", "Measured quantity", "text"),
        field("interface", "Interface", "dropdown", options=["Analog", "Digital", "I2C", "SPI", "UART", "1-Wire", "Other"]),
        field("supply_voltage", "Supply voltage", "text"),
        field("package", "Package / module", "text"),
    ],
}


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


def seed_builtin_template_fields(db: Session) -> int:
    created = 0

    part_types = {
        part_type.name: part_type
        for part_type in db.query(PartType).filter(PartType.is_builtin.is_(True)).all()
    }

    for part_type_name, fields in BUILTIN_TEMPLATE_FIELDS.items():
        part_type = part_types.get(part_type_name)
        if part_type is None:
            continue

        existing_field_keys = {
            row.field_key
            for row in db.query(PartTypeField.field_key)
            .filter(PartTypeField.part_type_id == part_type.id)
            .all()
        }

        for sort_order, field_def in enumerate(fields, start=10):
            if field_def["field_key"] in existing_field_keys:
                continue

            db.add(
                PartTypeField(
                    part_type_id=part_type.id,
                    field_key=field_def["field_key"],
                    label=field_def["label"],
                    field_type=field_def["field_type"],
                    is_required=field_def["is_required"],
                    sort_order=sort_order * 10,
                    options_json=field_def["options_json"],
                    default_unit=field_def["default_unit"],
                    help_text=field_def["help_text"],
                )
            )
            created += 1

    db.commit()
    return created


def seed_default_app_settings(db: Session) -> int:
    created = 0

    existing_keys = {row.key for row in db.query(AppSetting.key).all()}

    for key, values in DEFAULT_APP_SETTINGS.items():
        if key in existing_keys:
            continue

        db.add(
            AppSetting(
                key=key,
                value_json=values.get("value_json"),
                value_text=values.get("value_text"),
            )
        )
        created += 1

    db.commit()
    return created


def main() -> None:
    db = SessionLocal()
    try:
        created_types = seed_builtin_part_types(db)
        created_fields = seed_builtin_template_fields(db)
        created_settings = seed_default_app_settings(db)
        print(f"Seeded built-in part types. Created: {created_types}")
        print(f"Seeded built-in template fields. Created: {created_fields}")
        print(f"Seeded default app settings. Created: {created_settings}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
