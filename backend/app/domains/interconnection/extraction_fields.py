"""What extraction looks for in an interconnection packet. Names are stable: reconciliation keys off them."""

from app.core.extraction import FieldKind, FieldSpec

N, T, C = FieldKind.NUMBER, FieldKind.TEXT, FieldKind.CHOICE

FIELDS: tuple[FieldSpec, ...] = (
    # identity
    FieldSpec("applicant_name", T, "Customer / applicant name"),
    FieldSpec("site_address", T, "Service address where the generating facility is installed"),
    FieldSpec("installer_name", T, "Installer or contractor company name"),
    # system totals as stated
    FieldSpec("system_ac_rating", N, "Total AC (gross nameplate) rating of the generating facility as stated", "power"),
    FieldSpec("system_apparent_power_rating", N, "Total apparent power (gross) rating of the facility as stated", "apparent_power"),
    FieldSpec("system_dc_rating", N, "Total PV array DC rating", "dc_power"),
    # inverter, per unit
    FieldSpec("inverter_manufacturer", T, "Inverter manufacturer"),
    FieldSpec("inverter_model", T, "Inverter model number"),
    FieldSpec("inverter_quantity", N, "Number of inverters of this model", "count"),
    FieldSpec("inverter_rated_ac_power", N, "Rated (continuous) AC output power of one inverter", "power"),
    FieldSpec("inverter_max_apparent_power", N, "Maximum apparent power of one inverter", "apparent_power"),
    FieldSpec("inverter_max_continuous_output_current", N, "Maximum continuous AC output current of one inverter", "current"),
    FieldSpec("inverter_max_fault_current", N, "Maximum output fault current (short-circuit contribution) of one inverter", "current"),
    FieldSpec("inverter_nominal_ac_voltage", N, "Nominal AC output voltage of the inverter", "voltage"),
    FieldSpec("inverter_certification", T, "Certification standard the inverter is listed to, e.g. UL 1741 SB or IEEE 1547"),
    FieldSpec("inverter_phase_configuration", C, "How the inverter connects",
              choices=("single_phase_240v_split", "single_phase_120v", "three_phase")),
    # storage
    FieldSpec("battery_manufacturer", T, "Battery / energy storage manufacturer"),
    FieldSpec("battery_model", T, "Battery model number"),
    FieldSpec("battery_usable_capacity", N, "Usable energy capacity of the storage system", "energy"),
    FieldSpec("battery_rated_power", N, "Rated continuous power of the storage system", "power"),
    # service and operation
    FieldSpec("service_panel_rating", N, "Ampere rating of the customer's main service equipment / panel", "current"),
    FieldSpec("service_voltage", N, "Service voltage", "voltage"),
    FieldSpec("service_phases", N, "Number of service phases (1 or 3)", "count"),
    FieldSpec("export_intent", C, "Whether the facility will export power to the grid", choices=("export", "non_export")),
    FieldSpec("non_export_option", N, "Rule 21 Screen I non-export or limited-export option number selected", "count"),
    FieldSpec("tariff_program", C, "Tariff the facility interconnects under", choices=("NEM-1", "NEM-2", "NBT-1", "other")),
    FieldSpec("min_host_load_12mo", N, "Verifiable minimum host load over the past 12 months", "power"),
)
