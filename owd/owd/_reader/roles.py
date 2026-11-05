# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Free for non-commercial use; companies need a licence (see NOTICE).
"""Physical role of each channel (to check the dimension of its unit) and blacklist of ambiguous channels.

Source of the Volve roles: the `role` column of the Volve channel table in the Volve/FORGE inventory, which comes from
each file's own `curveDescription`. Only the mnemonics of those roles are listed here; every other channel has no role
and is read without a dimension check.

A blacklisted channel is read only if it is asked for by name and also included in `allow`.
"""
import re

# role -> dimension its unit must have
ROLE_DIM = {"RPM": "angular_velocity", "TQ": "torque", "WOB": "force", "HKL": "force", "SPP": "pressure",
            "FLOW": "flow_rate", "BITDEP": "length", "HOLEDEP": "length", "ROP": "velocity",
            "DH_RPM": "angular_velocity", "DH_TQ": "torque", "DH_WOB": "force",
            "MOTOR": "angular_velocity"}

# Volve: mnemonic -> role (inventory). ROP, ROP5 and ROP_AVG have no role in the inventory; they get role ROP from
# their curveDescription: "Rate of Penetration", "Rate of Penetration (5ft avg)", "Depth Averaged ROP" /
# "Time Averaged ROP".
ROLES_VOLVE = {
    **{m: "RPM" for m in ("RPM", "SURF_RPM", "GS_RPM")},
    **{m: "TQ" for m in ("TQA", "TORQUE_AVG", "TORQUE", "TORQUE_MAX", "TORQUE_MIN", "GS_TQA")},
    **{m: "WOB" for m in ("SWOB", "WOB_AVG", "WOB", "WOB_MAX", "WOB_MIN", "CWOB", "GS_SWOB")},
    **{m: "HKL" for m in ("HKLD", "HKLD_AVG", "HKLD_MAX", "HKLD_MIN", "THKD", "GS_HKLD")},
    **{m: "SPP" for m in ("SPPA", "PUMP", "PUMP_AVG", "PUMP_MAX", "PUMP_MIN", "GS_SPPA")},
    **{m: "FLOW" for m in ("TFLO", "FLOWIN", "GS_TFLO")},
    **{m: "BITDEP" for m in ("DBTM", "BITDEP", "GS_DBTM")},
    **{m: "HOLEDEP" for m in ("DMEA", "MDEPTH")},
    **{m: "ROP" for m in ("ROP", "ROP_AVG", "ROP5")},
    **{m: "DH_RPM" for m in ("CRPM_RT", "SSRPMAVM", "SSRPMAXM", "SSRPMINM", "DLC_RPMX", "RPMAX", "RPMX")},
    "DTOR_RT": "DH_TQ", "DWOB_RT": "DH_WOB", "MOTOR_RPM": "MOTOR",
}

# FORGE: regex on the column name without its unit (Pason EDR, Sanvean "Surface_*", *_standard files).
ROLES_FORGE = [
    ("RPM", r"^(Surface_)?(Top Drive RPM|Rotary RPM|Rotary Revolutions per Minute|Top Drive Revolutions per Minute)$"),
    ("TQ", r"^(Surface_)?(Top Drive Torque|Rotary Torque|Convertible Torque)$"),
    ("WOB", r"^(Surface_)?Weight on Bit$"),
    ("HKL", r"^(Surface_)?Hook ?[Ll]oad$"),
    ("SPP", r"^(Surface_)?(Standpipe Pressure|Pump Pressure)$"),
    ("FLOW", r"^(Surface_)?(Flow In|Total Pump Output)$"),
    ("BITDEP", r"^(Surface_)?(Bit Depth|Depth - Bit)$"),
    ("HOLEDEP", r"^(Surface_)?(Hole Depth|Total Depth)$"),
    ("DH_RPM", r"^(Top Sub|Bit Box|Lower Mandrel|Puk)_GyroX(max|min|med|rms)$"),
]

# Blacklist. Volve: DRPM is "Total Downhole RPM" in the WITSML but "SRF THDRPM 2hz" in the F-4 DLIS; BIT_RPM* is
# "Bit RPM - Total RPM", possibly surface + motor.
BLACKLIST_VOLVE = {
    "DRPM": "ambiguous: 'Total Downhole RPM' in WITSML, 'SRF THDRPM 2hz' in the F-4 DLIS",
    **{m: "BIT_RPM: 'Bit RPM - Total RPM', possibly surface + motor (E6)"
       for m in ("BIT_RPM", "BIT_RPM_AVG", "BIT_RPM_MAX", "BIT_RPM_MIN", "Bit_RPM", "ATK_BITRPMX")},
}
# FORGE: "downhole EDR" columns whose origin (MWD, model or calculation) is undocumented (E7).
BLACKLIST_FORGE = [
    (r"^(Bit RPM|Bit Revolutions per Minute)$", "downhole EDR channel with undocumented origin (E7)"),
    (r"^Downhole Torque$", "downhole EDR channel with undocumented origin (E7)"),
    (r"^Bit Torque$", "downhole EDR channel with undocumented origin (E7)"),
    (r"^DAS Bit RPM (Max|Min)$", "downhole EDR channel with undocumented origin (same rule as E7)"),
]


class AmbiguousChannel(ValueError):
    """A blacklisted channel was asked for without including it in `allow`."""


def role_of(name, source):
    """Role of the channel (or None). source = 'volve' (WITSML/LAS/DLIS mnemonic) or 'forge' (column name without unit)."""
    if source == "volve":
        return ROLES_VOLVE.get(name)
    for role, pat in ROLES_FORGE:
        if re.search(pat, name):
            return role
    return None


def blacklist_reason(name, source):
    """Reason if the channel is blacklisted, otherwise None."""
    if source == "volve":
        return BLACKLIST_VOLVE.get(name)
    for pat, why in BLACKLIST_FORGE:
        if re.search(pat, name):
            return why
    return None
