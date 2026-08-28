"""Generate a deterministic synthetic multifamily portfolio in DuckDB.

The schema is intentionally generic and does not represent a proprietary Yardi
schema. Public HUD FMR values are clearly separated from synthetic operations.
"""

from __future__ import annotations

import argparse
import calendar
import os
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import duckdb
import pandas as pd

from pma import WAREHOUSE_PATH

DEFAULT_SEED = 20260828
DEFAULT_AS_OF = date(2026, 6, 30)
HISTORY_MONTHS = 36
MONEY = Decimal("0.01")
PROVENANCE_COLUMNS = ("source_system", "source_record_id", "source_loaded_at", "is_synthetic")

# Fictional names keep dashboard examples readable without introducing real tenant
# information. The index-based selection preserves reproducibility for a given seed.
TENANT_FIRST_NAMES = (
    "Avery",
    "Jordan",
    "Morgan",
    "Taylor",
    "Riley",
    "Cameron",
    "Casey",
    "Quinn",
    "Drew",
    "Parker",
    "Reese",
    "Alex",
    "Bailey",
    "Blair",
    "Brooklyn",
    "Charlie",
    "Dakota",
    "Emerson",
    "Finley",
    "Frankie",
    "Gray",
    "Harper",
    "Hayden",
    "Jaden",
    "Jamie",
    "Jesse",
    "Kai",
    "Kendall",
    "Kerry",
    "Kieran",
    "Lennon",
    "Logan",
    "London",
    "Mackenzie",
    "Marley",
    "Micah",
    "Nico",
    "Noel",
    "Oakley",
    "Payton",
    "Phoenix",
    "Peyton",
    "Presley",
    "Rory",
    "Rowan",
    "Sage",
    "Sam",
    "Sawyer",
    "Shawn",
    "Shiloh",
    "Skyler",
    "Sloan",
    "Spencer",
    "Tatum",
    "Teagan",
    "Terry",
    "Val",
    "Winter",
    "Wren",
    "Zion",
    "Addison",
    "Amari",
    "Ari",
    "Aubrey",
    "Briar",
    "Dylan",
    "Elliot",
    "Ellis",
    "Jules",
    "Remy",
)
TENANT_LAST_NAMES = (
    "Bennett",
    "Brooks",
    "Carter",
    "Dawson",
    "Ellis",
    "Foster",
    "Hayes",
    "Jordan",
    "Morris",
    "Reed",
    "Sullivan",
    "Warren",
    "Adams",
    "Anderson",
    "Andrews",
    "Armstrong",
    "Bailey",
    "Baker",
    "Barnes",
    "Bell",
    "Bishop",
    "Black",
    "Boone",
    "Bradley",
    "Brady",
    "Briggs",
    "Brown",
    "Bryant",
    "Burke",
    "Burns",
    "Butler",
    "Byrd",
    "Campbell",
    "Carroll",
    "Chapman",
    "Chase",
    "Clark",
    "Clay",
    "Cole",
    "Collins",
    "Conley",
    "Conner",
    "Cooper",
    "Cox",
    "Craig",
    "Cross",
    "Cummings",
    "Curtis",
    "Daniels",
    "Davidson",
    "Davis",
    "Decker",
    "Diaz",
    "Dixon",
    "Douglas",
    "Drake",
    "Duncan",
    "Dunn",
    "Edwards",
    "Evans",
    "Ferguson",
    "Fields",
    "Fisher",
    "Fleming",
    "Fletcher",
    "Ford",
    "Fox",
    "Franklin",
    "Freeman",
    "Fuller",
    "Gibson",
    "Gilbert",
    "Glover",
    "Goodwin",
    "Gordon",
    "Graham",
    "Grant",
    "Graves",
    "Green",
    "Greer",
    "Griffin",
    "Gross",
    "Hahn",
    "Hall",
    "Hampton",
    "Hancock",
    "Hansen",
    "Hardy",
    "Harmon",
    "Harvey",
    "Hawkins",
)


def _tenant_name(tenant_number: int) -> str:
    if tenant_number < 1 or tenant_number > len(TENANT_FIRST_NAMES) * len(TENANT_LAST_NAMES):
        raise ValueError("tenant name pool exhausted")
    first_name = TENANT_FIRST_NAMES[(tenant_number - 1) % len(TENANT_FIRST_NAMES)]
    last_name = TENANT_LAST_NAMES[
        (tenant_number - 1) // len(TENANT_FIRST_NAMES) % len(TENANT_LAST_NAMES)
    ]
    return f"{first_name} {last_name}"


def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def _months(start: date, end: date) -> Iterable[date]:
    current = _month_start(start)
    while current <= _month_start(end):
        yield current
        current = _add_months(current, 1)


def _provenance(source: str, record_id: str, loaded_at: datetime, synthetic: bool = True) -> tuple:
    return source, record_id, loaded_at, synthetic


TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "properties": (
        "property_id",
        "property_name",
        "market_id",
        "county_name",
        "state_code",
        "property_class",
        "year_built",
        "unit_count",
        "active_from",
        "active_to",
        *PROVENANCE_COLUMNS,
    ),
    "units": (
        "unit_id",
        "property_id",
        "unit_number",
        "bedrooms",
        "bathrooms",
        "square_feet",
        "market_rent",
        "is_rentable",
        "active_from",
        "active_to",
        *PROVENANCE_COLUMNS,
    ),
    "tenants": ("tenant_id", "tenant_name", "created_date", *PROVENANCE_COLUMNS),
    "leases": (
        "lease_id",
        "property_id",
        "unit_id",
        "tenant_id",
        "lease_start_date",
        "lease_end_date",
        "move_in_date",
        "move_out_date",
        "signed_date",
        "monthly_rent",
        "status",
        "renewal_of_lease_id",
        "outcome",
        *PROVENANCE_COLUMNS,
    ),
    "charges": (
        "charge_id",
        "property_id",
        "unit_id",
        "lease_id",
        "tenant_id",
        "charge_date",
        "due_date",
        "charge_type",
        "amount",
        "approved_credit_amount",
        "posted_at",
        *PROVENANCE_COLUMNS,
    ),
    "payments": (
        "payment_id",
        "property_id",
        "tenant_id",
        "payment_date",
        "amount",
        "payment_method",
        "status",
        "posted_at",
        *PROVENANCE_COLUMNS,
    ),
    "payment_allocations": (
        "payment_allocation_id",
        "payment_id",
        "charge_id",
        "allocated_amount",
        "allocation_date",
        *PROVENANCE_COLUMNS,
    ),
    "gl_entries": (
        "gl_entry_id",
        "journal_id",
        "property_id",
        "posting_date",
        "account_code",
        "account_name",
        "account_type",
        "debit_amount",
        "credit_amount",
        "work_order_id",
        "description",
        *PROVENANCE_COLUMNS,
    ),
    "budgets": (
        "budget_id",
        "property_id",
        "budget_month",
        "account_code",
        "account_name",
        "account_type",
        "budget_amount",
        *PROVENANCE_COLUMNS,
    ),
    "vendors": (
        "vendor_id",
        "vendor_name",
        "specialty",
        "active_from",
        "active_to",
        *PROVENANCE_COLUMNS,
    ),
    "work_orders": (
        "work_order_id",
        "property_id",
        "unit_id",
        "vendor_id",
        "opened_at",
        "first_response_at",
        "closed_at",
        "status",
        "priority",
        "category",
        "maintenance_type",
        "description",
        "labor_cost",
        "material_cost",
        "vendor_cost",
        *PROVENANCE_COLUMNS,
    ),
    "work_order_status_history": (
        "status_event_id",
        "work_order_id",
        "status",
        "event_at",
        "event_sequence",
        *PROVENANCE_COLUMNS,
    ),
    "hud_fmr": (
        "market_id",
        "county_name",
        "state_code",
        "bedrooms",
        "fiscal_year",
        "fmr_amount",
        "benchmark_label",
        "source_url",
        *PROVENANCE_COLUMNS,
    ),
    "raw_data_quality_issues": (
        "issue_id",
        "issue_code",
        "affected_table",
        "affected_record_id",
        "expected_handling",
        "description",
        *PROVENANCE_COLUMNS,
    ),
}


DDL = """
CREATE SCHEMA raw;
CREATE TABLE raw.properties (
  property_id VARCHAR, property_name VARCHAR, market_id VARCHAR, county_name VARCHAR,
  state_code VARCHAR, property_class VARCHAR, year_built INTEGER, unit_count INTEGER,
  active_from DATE, active_to DATE, source_system VARCHAR, source_record_id VARCHAR,
  source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.units (
  unit_id VARCHAR, property_id VARCHAR, unit_number VARCHAR, bedrooms INTEGER,
  bathrooms DECIMAL(3,1), square_feet INTEGER, market_rent DECIMAL(18,2), is_rentable BOOLEAN,
  active_from DATE, active_to DATE, source_system VARCHAR, source_record_id VARCHAR,
  source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.tenants (
  tenant_id VARCHAR, tenant_name VARCHAR, created_date DATE, source_system VARCHAR,
  source_record_id VARCHAR, source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.leases (
  lease_id VARCHAR, property_id VARCHAR, unit_id VARCHAR, tenant_id VARCHAR,
  lease_start_date DATE, lease_end_date DATE, move_in_date DATE, move_out_date DATE,
  signed_date DATE, monthly_rent DECIMAL(18,2), status VARCHAR, renewal_of_lease_id VARCHAR,
  outcome VARCHAR, source_system VARCHAR, source_record_id VARCHAR,
  source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.charges (
  charge_id VARCHAR, property_id VARCHAR, unit_id VARCHAR, lease_id VARCHAR, tenant_id VARCHAR,
  charge_date DATE, due_date DATE, charge_type VARCHAR, amount DECIMAL(18,2),
  approved_credit_amount DECIMAL(18,2), posted_at TIMESTAMP, source_system VARCHAR,
  source_record_id VARCHAR, source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.payments (
  payment_id VARCHAR, property_id VARCHAR, tenant_id VARCHAR, payment_date DATE,
  amount DECIMAL(18,2), payment_method VARCHAR, status VARCHAR, posted_at TIMESTAMP,
  source_system VARCHAR, source_record_id VARCHAR, source_loaded_at TIMESTAMP,
  is_synthetic BOOLEAN
);
CREATE TABLE raw.payment_allocations (
  payment_allocation_id VARCHAR, payment_id VARCHAR, charge_id VARCHAR,
  allocated_amount DECIMAL(18,2), allocation_date DATE, source_system VARCHAR,
  source_record_id VARCHAR, source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.gl_entries (
  gl_entry_id VARCHAR, journal_id VARCHAR, property_id VARCHAR, posting_date DATE,
  account_code VARCHAR, account_name VARCHAR, account_type VARCHAR,
  debit_amount DECIMAL(18,2), credit_amount DECIMAL(18,2), work_order_id VARCHAR,
  description VARCHAR, source_system VARCHAR, source_record_id VARCHAR,
  source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.budgets (
  budget_id VARCHAR, property_id VARCHAR, budget_month DATE, account_code VARCHAR,
  account_name VARCHAR, account_type VARCHAR, budget_amount DECIMAL(18,2),
  source_system VARCHAR, source_record_id VARCHAR, source_loaded_at TIMESTAMP,
  is_synthetic BOOLEAN
);
CREATE TABLE raw.vendors (
  vendor_id VARCHAR, vendor_name VARCHAR, specialty VARCHAR, active_from DATE, active_to DATE,
  source_system VARCHAR, source_record_id VARCHAR, source_loaded_at TIMESTAMP,
  is_synthetic BOOLEAN
);
CREATE TABLE raw.work_orders (
  work_order_id VARCHAR, property_id VARCHAR, unit_id VARCHAR, vendor_id VARCHAR,
  opened_at TIMESTAMP, first_response_at TIMESTAMP, closed_at TIMESTAMP, status VARCHAR,
  priority VARCHAR, category VARCHAR, maintenance_type VARCHAR, description VARCHAR,
  labor_cost DECIMAL(18,2), material_cost DECIMAL(18,2), vendor_cost DECIMAL(18,2),
  source_system VARCHAR, source_record_id VARCHAR, source_loaded_at TIMESTAMP,
  is_synthetic BOOLEAN
);
CREATE TABLE raw.work_order_status_history (
  status_event_id VARCHAR, work_order_id VARCHAR, status VARCHAR, event_at TIMESTAMP,
  event_sequence INTEGER, source_system VARCHAR, source_record_id VARCHAR,
  source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
CREATE TABLE raw.hud_fmr (
  market_id VARCHAR, county_name VARCHAR, state_code VARCHAR, bedrooms INTEGER,
  fiscal_year INTEGER, fmr_amount DECIMAL(18,2), benchmark_label VARCHAR, source_url VARCHAR,
  source_system VARCHAR, source_record_id VARCHAR, source_loaded_at TIMESTAMP,
  is_synthetic BOOLEAN
);
CREATE TABLE raw.raw_data_quality_issues (
  issue_id VARCHAR, issue_code VARCHAR, affected_table VARCHAR, affected_record_id VARCHAR,
  expected_handling VARCHAR, description VARCHAR, source_system VARCHAR,
  source_record_id VARCHAR, source_loaded_at TIMESTAMP, is_synthetic BOOLEAN
);
"""


def _insert(connection: duckdb.DuckDBPyConnection, table: str, rows: Sequence[tuple]) -> None:
    columns = TABLE_COLUMNS[table]
    frame = pd.DataFrame.from_records(rows, columns=columns)
    connection.register("_generated_rows", frame)
    names = ", ".join(columns)
    connection.execute(f"INSERT INTO raw.{table} ({names}) SELECT {names} FROM _generated_rows")
    connection.unregister("_generated_rows")


def _portfolio(
    as_of: date, loaded_at: datetime
) -> tuple[list[tuple], list[tuple], dict[str, list[str]]]:
    markets = (
        ("ATL", "Fulton County", "GA"),
        ("DFW", "Dallas County", "TX"),
        ("PHX", "Maricopa County", "AZ"),
        ("TPA", "Hillsborough County", "FL"),
    )
    sizes = (96, 110, 124, 132, 148, 144)
    properties: list[tuple] = []
    units: list[tuple] = []
    units_by_property: dict[str, list[str]] = defaultdict(list)
    global_unit = 0
    for market_index, (market, county, state) in enumerate(markets):
        for property_index in range(6):
            property_class = "A" if property_index < 3 else "B"
            cohort_number = property_index + 1 if property_class == "A" else property_index - 2
            property_id = f"{market}-{property_class}{cohort_number:02d}"
            unit_count = sizes[property_index]
            active_to = _month_end(_add_months(as_of, -3)) if property_id == "TPA-B03" else None
            properties.append(
                (
                    property_id,
                    f"{market} {property_class} Community {cohort_number}",
                    market,
                    county,
                    state,
                    property_class,
                    2014 - property_index * 4 + market_index,
                    unit_count,
                    date(2018, 1, 1),
                    active_to,
                    *_provenance("synthetic_property_master", property_id, loaded_at),
                )
            )
            class_base = 1725 if property_class == "A" else 1375
            market_adjustment = (80, 30, 20, 60)[market_index]
            for local_unit in range(1, unit_count + 1):
                global_unit += 1
                unit_id = f"UNIT-{global_unit:05d}"
                bedrooms = (local_unit + property_index) % 4
                bathrooms = Decimal("1.0") if bedrooms < 2 else Decimal("2.0")
                square_feet = 525 + bedrooms * 260 + (local_unit % 7) * 15
                market_rent = _money(
                    class_base + market_adjustment + bedrooms * 310 + local_unit % 11 * 8
                )
                units.append(
                    (
                        unit_id,
                        property_id,
                        f"{local_unit:04d}",
                        bedrooms,
                        bathrooms,
                        square_feet,
                        market_rent,
                        True,
                        date(2018, 1, 1),
                        active_to,
                        *_provenance("synthetic_unit_master", unit_id, loaded_at),
                    )
                )
                units_by_property[property_id].append(unit_id)
    return properties, units, units_by_property


def _lease_data(
    units: Sequence[tuple], as_of: date, loaded_at: datetime
) -> tuple[list[tuple], list[tuple], dict[str, list[tuple]]]:
    forecast_end = _add_months(_month_end(as_of), 12)
    history_start = _add_months(_month_start(as_of), -(HISTORY_MONTHS - 1))
    tenants: list[tuple] = []
    leases: list[tuple] = []
    leases_by_unit: dict[str, list[tuple]] = defaultdict(list)
    tenant_counter = 0
    lease_counter = 0
    for unit_index, unit in enumerate(units):
        unit_id, property_id, _, _, _, _, market_rent = unit[:7]
        local_index = int(unit[2])
        if property_id == "PHX-B02" and local_index <= 72:
            offset = (10, 9)[local_index % 2]
        else:
            offset = unit_index % 12
        start = _add_months(history_start, -offset)
        previous_lease_id: str | None = None
        tenant_id: str | None = None
        sequence = 0
        rent = _money(Decimal(market_rent) * Decimal("0.91"))
        while start <= forecast_end:
            end = _add_months(start, 12) - timedelta(days=1)
            if tenant_id is None:
                tenant_counter += 1
                tenant_id = f"TEN-{tenant_counter:06d}"
                tenants.append(
                    (
                        tenant_id,
                        _tenant_name(tenant_counter),
                        start - timedelta(days=45),
                        *_provenance("synthetic_tenant_master", tenant_id, loaded_at),
                    )
                )
            lease_counter += 1
            lease_id = f"LEASE-{lease_counter:06d}"
            renewal = (unit_index + sequence) % 4 != 0
            vacancy_days = 0 if renewal else 14 + (unit_index * 7 + sequence * 11) % 43
            next_start = end + timedelta(days=1 + vacancy_days)
            special_pending = (
                property_id == "PHX-B02"
                and as_of < end <= as_of + timedelta(days=92)
                and local_index <= 72
            )
            signed_next = next_start - timedelta(days=35 + (unit_index % 20))
            has_known_successor = end <= as_of or (end <= forecast_end and signed_next <= as_of)
            if special_pending:
                has_known_successor = False
            if end < as_of:
                status = "ended"
                outcome = "renewed" if renewal else "turned_over"
                move_out = None if renewal else end
            elif start <= as_of <= end:
                status = "active"
                outcome = (
                    ("renewed" if renewal else "turned_over") if has_known_successor else "pending"
                )
                move_out = None
            else:
                status = "future"
                outcome = "pending"
                move_out = None
            row = (
                lease_id,
                property_id,
                unit_id,
                tenant_id,
                start,
                end,
                start,
                move_out,
                start - timedelta(days=45),
                rent,
                status,
                previous_lease_id,
                outcome,
                *_provenance("synthetic_lease_ledger", lease_id, loaded_at),
            )
            leases.append(row)
            leases_by_unit[unit_id].append(row)
            if not has_known_successor and end > as_of:
                break
            previous_lease_id = lease_id
            start = next_start
            if not renewal:
                tenant_id = None
            rent = _money(rent * Decimal("1.04"))
            sequence += 1
    return tenants, leases, leases_by_unit


def _vendors(loaded_at: datetime) -> list[tuple]:
    specialties = ("HVAC", "Plumbing", "Electrical", "General", "Landscaping", "Appliance")
    rows = []
    for specialty in specialties:
        for variant in range(1, 4):
            vendor_id = f"VEND-{specialty.upper()[:4]}-{variant:02d}"
            rows.append(
                (
                    vendor_id,
                    f"Synthetic {specialty} Partner {variant}",
                    specialty,
                    date(2020, 1, 1),
                    None,
                    *_provenance("synthetic_vendor_master", vendor_id, loaded_at),
                )
            )
    return rows


def _work_order_data(
    rng: random.Random,
    properties: Sequence[tuple],
    units_by_property: dict[str, list[str]],
    as_of: date,
    loaded_at: datetime,
) -> tuple[list[tuple], list[tuple], dict[tuple[str, date], Decimal], str]:
    start = _add_months(_month_start(as_of), -(HISTORY_MONTHS - 1))
    categories = ("HVAC", "Plumbing", "Electrical", "General", "Appliance")
    priorities = ("low", "normal", "normal", "normal", "high", "emergency")
    work_orders: list[tuple] = []
    history: list[tuple] = []
    costs_by_property_month: dict[tuple[str, date], Decimal] = defaultdict(lambda: Decimal("0.00"))
    counter = 0
    reopened_work_order = ""

    def add_work_order(
        property_id: str,
        unit_id: str,
        opened: datetime,
        category: str,
        priority: str,
        maintenance_type: str = "reactive",
        force_open: bool = False,
        vendor_variant: int | None = None,
        missing_vendor: bool = False,
    ) -> None:
        nonlocal counter, reopened_work_order
        counter += 1
        work_order_id = f"WO-{counter:06d}"
        response_hours = {"emergency": 1, "high": 6, "normal": 18, "low": 36}[priority]
        response_hours += rng.randint(0, 10)
        duration_hours = {"emergency": 16, "high": 30, "normal": 54, "low": 80}[priority]
        duration_hours += rng.randint(0, 80)
        if property_id == "DFW-A03" and opened.date() >= _add_months(_month_start(as_of), -3):
            duration_hours *= 4
            force_open = force_open or counter % 2 == 0
        variant = vendor_variant or (counter % 3 + 1)
        vendor_id = f"VEND-{category.upper()[:4]}-{variant:02d}"
        if missing_vendor:
            vendor_id = None
        first_response = opened + timedelta(hours=response_hours)
        closed = None if force_open else opened + timedelta(hours=duration_hours)
        if closed and closed.date() > as_of:
            closed = None
        status = "open" if closed is None else "closed"
        labor = _money(65 + duration_hours * Decimal("1.15"))
        material = _money(25 + (counter * 13) % 280)
        vendor_cost = _money(80 + (counter * 29) % 520)
        if property_id == "TPA-A02" and category == "HVAC" and variant == 3:
            vendor_cost = _money(vendor_cost * Decimal("2.20"))
            if closed:
                closed += timedelta(hours=48)
        work_orders.append(
            (
                work_order_id,
                property_id,
                unit_id,
                vendor_id,
                opened,
                first_response,
                closed,
                status,
                priority,
                category,
                maintenance_type,
                f"Synthetic {category.lower()} service request",
                labor,
                material,
                vendor_cost,
                *_provenance("synthetic_work_order_system", work_order_id, loaded_at),
            )
        )
        events = [("opened", opened), ("in_progress", first_response)]
        if closed:
            events.append(("closed", closed))
        for event_sequence, (event_status, event_at) in enumerate(events, 1):
            event_id = f"WOEV-{counter:06d}-{event_sequence}"
            history.append(
                (
                    event_id,
                    work_order_id,
                    event_status,
                    event_at,
                    event_sequence,
                    *_provenance("synthetic_work_order_system", event_id, loaded_at),
                )
            )
        costs_by_property_month[(property_id, _month_start(opened.date()))] += (
            labor + material + vendor_cost
        )
        if not reopened_work_order and property_id == "ATL-A01" and closed:
            reopened_work_order = work_order_id
            reopened_at = closed + timedelta(days=5)
            reclosed_at = reopened_at + timedelta(hours=30)
            for event_sequence, (event_status, event_at) in enumerate(
                (("reopened", reopened_at), ("closed", reclosed_at)), start=4
            ):
                event_id = f"WOEV-{counter:06d}-{event_sequence}"
                history.append(
                    (
                        event_id,
                        work_order_id,
                        event_status,
                        event_at,
                        event_sequence,
                        *_provenance("synthetic_work_order_system", event_id, loaded_at),
                    )
                )

    for property_row in properties:
        property_id, unit_count = property_row[0], property_row[7]
        unit_ids = units_by_property[property_id]
        for month_index, month in enumerate(_months(start, as_of)):
            summer = 1.45 if month.month in (6, 7, 8) else 1.0
            count = max(3, round(unit_count * 0.035 * summer))
            for item in range(count):
                category = categories[(item + month_index + len(property_id)) % len(categories)]
                if month.month in (6, 7, 8) and item % 3 == 0:
                    category = "HVAC"
                priority = priorities[(counter + item) % len(priorities)]
                day = 2 + (item * 5 + month_index) % 24
                opened = datetime.combine(month.replace(day=day), time(8 + item % 9, 0))
                force_open = (
                    property_id == "DFW-A03"
                    and month >= _add_months(_month_start(as_of), -2)
                    and item % 2 == 0
                )
                add_work_order(
                    property_id,
                    unit_ids[(item * 17 + month_index) % len(unit_ids)],
                    opened,
                    category,
                    priority,
                    "preventive" if item % 7 == 0 else "reactive",
                    force_open,
                )

    # Repeated HVAC requests on identical units within 90 days.
    for unit_id in units_by_property["ATL-B02"][:8]:
        for offset in (75, 35):
            opened = datetime.combine(as_of - timedelta(days=offset), time(9, 0))
            add_work_order("ATL-B02", unit_id, opened, "HVAC", "high")

    # Ensure enough comparable observations for the planted vendor outlier.
    for index in range(24):
        opened = datetime.combine(as_of - timedelta(days=170 - index * 5), time(10, 0))
        add_work_order(
            "TPA-A02",
            units_by_property["TPA-A02"][index],
            opened,
            "HVAC",
            "normal",
            vendor_variant=3,
        )

    return work_orders, history, costs_by_property_month, reopened_work_order


def _financial_data(
    rng: random.Random,
    properties: Sequence[tuple],
    units: Sequence[tuple],
    leases_by_unit: dict[str, list[tuple]],
    work_order_costs: dict[tuple[str, date], Decimal],
    as_of: date,
    loaded_at: datetime,
) -> tuple[list[tuple], list[tuple], list[tuple], list[tuple], list[tuple]]:
    start = _add_months(_month_start(as_of), -(HISTORY_MONTHS - 1))
    charges: list[tuple] = []
    payments: list[tuple] = []
    allocations: list[tuple] = []
    budgets: list[tuple] = []
    gl: list[tuple] = []
    property_units: dict[str, list[tuple]] = defaultdict(list)
    for unit in units:
        property_units[unit[1]].append(unit)
    charge_counter = payment_counter = allocation_counter = gl_counter = 0
    monthly_totals: dict[tuple[str, date], dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: Decimal("0.00"))
    )

    for property_row in properties:
        property_id = property_row[0]
        for month in _months(start, as_of):
            due_date = month
            for unit in property_units[property_id]:
                unit_id = unit[0]
                active_lease = next(
                    (
                        lease
                        for lease in leases_by_unit[unit_id]
                        if lease[4] <= due_date <= lease[5]
                    ),
                    None,
                )
                if active_lease is None:
                    continue
                lease_id, tenant_id, rent = (
                    active_lease[0],
                    active_lease[3],
                    Decimal(active_lease[9]),
                )
                charge_counter += 1
                charge_id = f"CHG-{charge_counter:07d}"
                credit = Decimal("0.00")
                if (
                    property_id == "ATL-A01"
                    and month >= _add_months(_month_start(as_of), -5)
                    and int(unit[2]) % 3 == 0
                ):
                    credit = _money(rent * Decimal("0.15"))
                posted_at = datetime.combine(due_date, time(0, 5))
                charges.append(
                    (
                        charge_id,
                        property_id,
                        unit_id,
                        lease_id,
                        tenant_id,
                        due_date,
                        due_date,
                        "rent",
                        rent,
                        credit,
                        posted_at,
                        *_provenance("synthetic_ar_ledger", charge_id, loaded_at),
                    )
                )
                net = rent - credit
                monthly_totals[(property_id, month)]["rent"] += net
                pay_ratio = Decimal("1.00")
                if property_id == "TPA-B01" and month >= _add_months(_month_start(as_of), -3):
                    if int(unit[2]) % 5 == 0:
                        pay_ratio = Decimal("0.00")
                    elif int(unit[2]) % 7 == 0:
                        pay_ratio = Decimal("0.50")
                elif (charge_counter + month.month) % 97 == 0:
                    pay_ratio = Decimal("0.50")
                paid = _money(net * pay_ratio)
                if paid <= 0:
                    continue
                payment_counter += 1
                payment_id = f"PAY-{payment_counter:07d}"
                payment_date = min(due_date + timedelta(days=3 + payment_counter % 7), as_of)
                payments.append(
                    (
                        payment_id,
                        property_id,
                        tenant_id,
                        payment_date,
                        paid,
                        ("ach", "check", "card")[payment_counter % 3],
                        "posted",
                        datetime.combine(payment_date, time(12, 0)),
                        *_provenance("synthetic_cash_receipts", payment_id, loaded_at),
                    )
                )
                allocation_counter += 1
                allocation_id = f"ALLOC-{allocation_counter:07d}"
                allocations.append(
                    (
                        allocation_id,
                        payment_id,
                        charge_id,
                        paid,
                        payment_date,
                        *_provenance("synthetic_cash_receipts", allocation_id, loaded_at),
                    )
                )
                monthly_totals[(property_id, month)]["payments"] += paid

            # Other property income preserves a realistic non-rent revenue stream.
            charge_counter += 1
            other_id = f"CHG-{charge_counter:07d}"
            other_amount = _money(property_row[7] * (42 + month.month % 4))
            charges.append(
                (
                    other_id,
                    property_id,
                    None,
                    None,
                    None,
                    month,
                    month,
                    "other_income",
                    other_amount,
                    Decimal("0.00"),
                    datetime.combine(month, time(0, 10)),
                    *_provenance("synthetic_ar_ledger", other_id, loaded_at),
                )
            )
            monthly_totals[(property_id, month)]["other"] += other_amount

            accounts = {
                "EXP_PAYROLL": ("Payroll", "expense", _money(property_row[7] * 118)),
                "EXP_UTILITIES": (
                    "Utilities",
                    "expense",
                    _money(property_row[7] * (43 + 8 * (month.month in (6, 7, 8)))),
                ),
                "EXP_REPAIRS": (
                    "Repairs and Maintenance",
                    "expense",
                    _money(work_order_costs[(property_id, month)]),
                ),
                "EXP_INSURANCE": ("Insurance", "expense", _money(property_row[7] * 31)),
                "EXP_TAXES": ("Property Taxes", "expense", _money(property_row[7] * 47)),
            }
            if property_id == "DFW-B03" and month >= _add_months(_month_start(as_of), -5):
                name, kind, value = accounts["EXP_UTILITIES"]
                accounts["EXP_UTILITIES"] = (name, kind, _money(value * Decimal("1.75")))
            for account, (_, _, value) in accounts.items():
                monthly_totals[(property_id, month)][account] = value

            revenue_budget = _money(
                property_row[7]
                * (Decimal("2150") if property_row[5] == "A" else Decimal("1720"))
                * Decimal("0.95")
            )
            budget_values = {
                "REV_RENT": ("Rental Revenue", "revenue", revenue_budget),
                "REV_OTHER": ("Other Operating Income", "revenue", _money(property_row[7] * 44)),
                **accounts,
            }
            for account_code, (account_name, account_type, actual_basis) in budget_values.items():
                if account_type == "expense":
                    budget_amount = _money(actual_basis * Decimal("0.96"))
                    if account_code == "EXP_UTILITIES" and property_id == "DFW-B03":
                        budget_amount = _money(
                            property_row[7]
                            * (43 + 8 * (month.month in (6, 7, 8)))
                            * Decimal("0.96")
                        )
                else:
                    budget_amount = actual_basis
                budget_id = f"BUD-{property_id}-{month:%Y%m}-{account_code}"
                budgets.append(
                    (
                        budget_id,
                        property_id,
                        month,
                        account_code,
                        account_name,
                        account_type,
                        budget_amount,
                        *_provenance("synthetic_budget_system", budget_id, loaded_at),
                    )
                )

    def journal(
        journal_id: str,
        property_id: str,
        posting_date: date,
        debit_account: tuple[str, str, str],
        credit_account: tuple[str, str, str],
        amount: Decimal,
        description: str,
    ) -> None:
        nonlocal gl_counter
        if amount == 0:
            return
        for account, debit, credit in (
            (debit_account, amount, Decimal("0.00")),
            (credit_account, Decimal("0.00"), amount),
        ):
            gl_counter += 1
            gl_id = f"GL-{gl_counter:07d}"
            gl.append(
                (
                    gl_id,
                    journal_id,
                    property_id,
                    posting_date,
                    account[0],
                    account[1],
                    account[2],
                    _money(debit),
                    _money(credit),
                    None,
                    description,
                    *_provenance("synthetic_general_ledger", gl_id, loaded_at),
                )
            )

    for (property_id, month), totals in sorted(monthly_totals.items()):
        rent = totals["rent"]
        other = totals["other"]
        payments_total = totals["payments"]
        journal(
            f"J-{property_id}-{month:%Y%m}-RENT",
            property_id,
            _month_end(month),
            ("ASSET_AR", "Accounts Receivable", "asset"),
            ("REV_RENT", "Rental Revenue", "revenue"),
            rent,
            "Monthly posted rental charges net of approved credits",
        )
        journal(
            f"J-{property_id}-{month:%Y%m}-OTHER",
            property_id,
            _month_end(month),
            ("ASSET_AR", "Accounts Receivable", "asset"),
            ("REV_OTHER", "Other Operating Income", "revenue"),
            other,
            "Monthly posted other operating income",
        )
        journal(
            f"J-{property_id}-{month:%Y%m}-CASH",
            property_id,
            _month_end(month),
            ("ASSET_CASH", "Cash", "asset"),
            ("ASSET_AR", "Accounts Receivable", "asset"),
            payments_total,
            "Monthly posted cash receipts",
        )
        for account_code, account_name in (
            ("EXP_PAYROLL", "Payroll"),
            ("EXP_UTILITIES", "Utilities"),
            ("EXP_REPAIRS", "Repairs and Maintenance"),
            ("EXP_INSURANCE", "Insurance"),
            ("EXP_TAXES", "Property Taxes"),
        ):
            journal(
                f"J-{property_id}-{month:%Y%m}-{account_code}",
                property_id,
                _month_end(month),
                (account_code, account_name, "expense"),
                ("ASSET_CASH", "Cash", "asset"),
                totals[account_code],
                f"Monthly posted {account_name.lower()}",
            )
    return charges, payments, allocations, gl, budgets


def _hud(loaded_at: datetime) -> list[tuple]:
    # Versioned demonstration subset of FY2026 county benchmarks; HUD is public context only.
    values = {
        "ATL": ("Fulton County", "GA", (1470, 1660, 1870, 2380)),
        "DFW": ("Dallas County", "TX", (1500, 1650, 1950, 2490)),
        "PHX": ("Maricopa County", "AZ", (1390, 1510, 1810, 2390)),
        "TPA": ("Hillsborough County", "FL", (1600, 1740, 2070, 2700)),
    }
    rows = []
    url = "https://www.huduser.gov/portal/datasets/fmr.html"
    for market, (county, state, rents) in values.items():
        for bedrooms, rent in enumerate(rents):
            source_id = f"HUD-FMR-2026-{market}-{bedrooms}BR"
            rows.append(
                (
                    market,
                    county,
                    state,
                    bedrooms,
                    2026,
                    _money(rent),
                    "HUD FY2026 40th-percentile gross-rent policy benchmark",
                    url,
                    *_provenance("hud_fmr_fy2026", source_id, loaded_at, synthetic=False),
                )
            )
    return rows


def _apply_quality_scenarios(
    connection: duckdb.DuckDBPyConnection, as_of: date, loaded_at: datetime
) -> None:
    """Apply known source defects directly to the persisted raw tables."""
    # Duplicate the exact source row so raw charges retain the planted defect.
    connection.execute(
        """
        insert into raw.charges
        select * from raw.charges
        where charge_id = 'CHG-0000101'
        limit 1
        """
    )

    # Add an overlapping lease using the existing ATL-A02 pending lease as its anchor.
    overlap_id = "DQ-LEASE-OVERLAP-001"
    connection.execute(
        """
        insert into raw.leases (
            lease_id, property_id, unit_id, tenant_id, lease_start_date, lease_end_date,
            move_in_date, move_out_date, signed_date, monthly_rent, status,
            renewal_of_lease_id, outcome, source_system, source_record_id,
            source_loaded_at, is_synthetic
        )
        select
            ?, property_id, unit_id, tenant_id, lease_start_date + interval 10 day,
            lease_end_date, move_in_date + interval 10 day, null, signed_date,
            monthly_rent, 'active', null, 'pending', 'synthetic_lease_ledger', ?, ?, true
        from raw.leases
        where property_id = 'ATL-A02' and outcome = 'pending'
        order by lease_id
        limit 1
        """,
        [overlap_id, overlap_id, loaded_at],
    )

    # Add a lease whose end date precedes its start date.
    invalid_id = "DQ-LEASE-DATES-001"
    invalid_start = _add_months(_month_start(as_of), -1)
    connection.execute(
        """
        insert into raw.leases (
            lease_id, property_id, unit_id, tenant_id, lease_start_date, lease_end_date,
            move_in_date, move_out_date, signed_date, monthly_rent, status,
            renewal_of_lease_id, outcome, source_system, source_record_id,
            source_loaded_at, is_synthetic
        )
        select
            ?, 'ATL-A03', unit_id, tenant_id, ?, ?, ?, null, ?, 1800, 'active',
            null, 'pending', 'synthetic_lease_ledger', ?, ?, true
        from raw.leases
        where property_id = 'ATL-A02' and outcome = 'pending'
        order by lease_id
        limit 1
        """,
        [
            invalid_id,
            invalid_start,
            invalid_start - timedelta(days=30),
            invalid_start,
            invalid_start - timedelta(days=60),
            invalid_id,
            loaded_at,
        ],
    )

    # Add an allocation pointing to a charge that does not exist.
    orphan_id = "DQ-ALLOC-ORPHAN-001"
    connection.execute(
        """
        insert into raw.payment_allocations (
            payment_allocation_id, payment_id, charge_id, allocated_amount,
            allocation_date, source_system, source_record_id, source_loaded_at, is_synthetic
        )
        select ?, payment_id, 'CHG-NOT-FOUND', 25, ?, 'synthetic_cash_receipts', ?, ?, true
        from raw.payment_allocations
        order by payment_allocation_id
        limit 1
        """,
        [orphan_id, as_of - timedelta(days=15), orphan_id, loaded_at],
    )

    # Add a balanced journal after TPA-B03 was inactivated.
    gl_id = "DQ-GL-INACTIVE-001"
    journal_id = "DQ-J-INACTIVE-001"
    connection.executemany(
        """
        insert into raw.gl_entries (
            gl_entry_id, journal_id, property_id, posting_date, account_code, account_name,
            account_type, debit_amount, credit_amount, work_order_id, description,
            source_system, source_record_id, source_loaded_at, is_synthetic
        ) values (?, ?, 'TPA-B03', ?, ?, ?, ?, ?, ?, null,
                  'Planted transaction after property inactivation',
                  'synthetic_general_ledger', ?, ?, true)
        """,
        [
            (
                f"{gl_id}-EXP_UTILITIES", journal_id,
                _month_end(_add_months(as_of, -1)), "EXP_UTILITIES", "Utilities", "expense",
                _money(100), _money(0), f"{gl_id}-EXP_UTILITIES", loaded_at,
            ),
            (
                f"{gl_id}-ASSET_CASH", journal_id,
                _month_end(_add_months(as_of, -1)), "ASSET_CASH", "Cash", "asset",
                _money(0), _money(100), f"{gl_id}-ASSET_CASH", loaded_at,
            ),
        ],
    )

    # Remove the vendor identifier from the first deterministic plumbing work order.
    connection.execute(
        """
        update raw.work_orders
        set vendor_id = null
        where work_order_id = (
            select work_order_id
            from raw.work_orders
            where category = 'Plumbing'
            order by work_order_id
            limit 1
        )
        """
    )


def generate_warehouse(
    output: Path, seed: int = DEFAULT_SEED, as_of: date = DEFAULT_AS_OF
) -> dict[str, int]:
    """Generate the raw warehouse and remove stale derived relations."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    loaded_at = datetime.combine(as_of, time(23, 59, 59))

    properties, units, units_by_property = _portfolio(as_of, loaded_at)
    tenants, leases, leases_by_unit = _lease_data(units, as_of, loaded_at)
    vendors = _vendors(loaded_at)
    work_orders, status_history, work_order_costs, reopened = _work_order_data(
        rng, properties, units_by_property, as_of, loaded_at
    )
    charges, payments, allocations, gl, budgets = _financial_data(
        rng, properties, units, leases_by_unit, work_order_costs, as_of, loaded_at
    )
    data = {
        "properties": properties,
        "units": units,
        "tenants": tenants,
        "leases": leases,
        "charges": charges,
        "payments": payments,
        "payment_allocations": allocations,
        "gl_entries": gl,
        "budgets": budgets,
        "vendors": vendors,
        "work_orders": work_orders,
        "work_order_status_history": status_history,
        "hud_fmr": _hud(loaded_at),
    }

    connection = duckdb.connect(str(output))
    try:
        # dbt does not drop relations for renamed or removed models.  Clear the
        # project-owned derived schemas before recreating the raw source so a
        # checked-in warehouse cannot retain stale, unused data between builds.
        for schema in (
            "main_base",
            "main_conformed",
            "main_core",
            "main_financial",
            "main_intermediate",
            "main_leasing",
            "main_operations",
            "main_staging",
        ):
            connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS raw CASCADE")
        connection.execute(DDL)
        for table, rows in data.items():
            _insert(connection, table, rows)
        _apply_quality_scenarios(connection, as_of, loaded_at)
        connection.execute("CHECKPOINT")
        counts = {
            table: connection.execute(f"select count(*) from raw.{table}").fetchone()[0]
            for table in TABLE_COLUMNS
        }
    finally:
        connection.close()
    return counts


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("PMA_WAREHOUSE_PATH", WAREHOUSE_PATH)),
        help="DuckDB output path (defaults to PMA_WAREHOUSE_PATH or data/warehouse.duckdb)",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of", type=_parse_date, default=DEFAULT_AS_OF)
    arguments = parser.parse_args()
    counts = generate_warehouse(arguments.output, arguments.seed, arguments.as_of)
    print(f"Generated {arguments.output} with seed={arguments.seed} as_of={arguments.as_of}")
    print("\n".join(f"  raw.{table}: {count:,}" for table, count in counts.items()))


if __name__ == "__main__":
    main()
