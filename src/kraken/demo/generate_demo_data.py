from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result

SEED = 20250820
PATIENT_COUNT = 2_500
SPELL_COUNT = 10_000
LAB_TEST_COUNT = 40_000


def _random_dates(
    rng: np.random.Generator, starts: pd.Series, end: pd.Timestamp
) -> pd.Series:
    start_days = starts.to_numpy(dtype="datetime64[D]").astype("int64")
    end_day = end.to_datetime64().astype("datetime64[D]").astype("int64")
    offsets = (rng.random(len(starts)) * (end_day - start_days + 1)).astype(int)
    return cast(pd.Series, pd.Series(pd.to_datetime(start_days + offsets, unit="D")))


def _build_patients(rng: np.random.Generator) -> pd.DataFrame:
    birth_start = pd.Timestamp("1930-01-01")
    birth_end = pd.Timestamp("2024-12-31")
    birth_days = (birth_end - birth_start).days
    dates_of_birth = pd.Series(
        birth_start
        + pd.to_timedelta(rng.integers(0, birth_days + 1, PATIENT_COUNT), unit="D")
    )
    age_days: pd.Series = (pd.Timestamp("2025-12-31") - dates_of_birth).dt.days
    ages_at_end = np.asarray(age_days, dtype=float) / 365.25
    ages_at_end = ages_at_end.astype(int)
    condition_rate = np.clip((ages_at_end - 25) / 30, 0.08, 3.5)

    return pd.DataFrame(
        {
            "patient_id": [
                f"PAT{number:06d}" for number in range(1, PATIENT_COUNT + 1)
            ],
            "patient_name": [
                f"Patient {number:05d}" for number in range(1, PATIENT_COUNT + 1)
            ],
            "date_of_birth": dates_of_birth,
            "sex": rng.choice(["Female", "Male"], PATIENT_COUNT, p=[0.51, 0.49]),
            "ethnicity": rng.choice(
                ["Asian", "Black", "Mixed", "Other", "White"],
                PATIENT_COUNT,
                p=[0.12, 0.08, 0.06, 0.04, 0.70],
            ),
            "imd_decile": rng.integers(1, 11, PATIENT_COUNT),
            "registered_region": rng.choice(
                ["Central", "East", "North", "South", "West"],
                PATIENT_COUNT,
                p=[0.20, 0.18, 0.23, 0.21, 0.18],
            ),
            "long_term_condition_count": np.clip(rng.poisson(condition_rate), 0, 8),
        }
    )


def _build_spells(rng: np.random.Generator, patients: pd.DataFrame) -> pd.DataFrame:
    ages_at_end = (
        (pd.Timestamp("2025-12-31") - patients["date_of_birth"]).dt.days / 365.25
    ).clip(lower=0)
    attendance_propensity = (
        0.6
        + patients["long_term_condition_count"] * 0.55
        + np.clip(ages_at_end - 60, 0, None) / 35
    )
    patient_indexes = rng.choice(
        patients.index,
        SPELL_COUNT,
        replace=True,
        p=attendance_propensity / attendance_propensity.sum(),
    )
    spell_patients = patients.loc[patient_indexes].reset_index(drop=True)

    eligible_starts = spell_patients["date_of_birth"].where(
        spell_patients["date_of_birth"] > pd.Timestamp("2022-01-01"),
        pd.Timestamp("2022-01-01"),
    )
    admission_dates = _random_dates(rng, eligible_starts, pd.Timestamp("2025-12-31"))
    age_days: pd.Series = (admission_dates - spell_patients["date_of_birth"]).dt.days
    ages = (np.asarray(age_days, dtype=float) / 365.25).astype(int)

    winter = admission_dates.dt.month.isin([1, 2, 11, 12]).astype(float)
    condition_counts = np.asarray(
        spell_patients["long_term_condition_count"], dtype=float
    )
    emergency_probability = np.clip(
        0.48 + winter * 0.10 + condition_counts * 0.025,
        0.35,
        0.82,
    )
    admission_methods = np.where(
        rng.random(SPELL_COUNT) < emergency_probability,
        "Emergency",
        rng.choice(
            ["Elective", "Maternity", "Transfer"], SPELL_COUNT, p=[0.72, 0.12, 0.16]
        ),
    )

    specialty = np.empty(SPELL_COUNT, dtype=object)
    for index, age in enumerate(ages):
        if age < 16:
            choices = ["Paediatrics", "General Medicine", "Orthopaedics"]
            probabilities = [0.72, 0.20, 0.08]
        elif age >= 70:
            choices = ["General Medicine", "Cardiology", "Respiratory", "Orthopaedics"]
            probabilities = [0.38, 0.25, 0.22, 0.15]
        else:
            choices = [
                "General Medicine",
                "Cardiology",
                "Respiratory",
                "Orthopaedics",
                "General Surgery",
            ]
            probabilities = [0.28, 0.18, 0.17, 0.18, 0.19]
        specialty[index] = rng.choice(choices, p=probabilities)

    diagnosis_by_specialty = {
        "Paediatrics": ["Viral infection", "Asthma", "Gastroenteritis"],
        "General Medicine": ["Sepsis", "Frailty", "Urinary infection"],
        "Cardiology": ["Heart failure", "Arrhythmia", "Chest pain"],
        "Respiratory": ["Pneumonia", "COPD exacerbation", "Asthma"],
        "Orthopaedics": ["Hip fracture", "Joint disorder", "Limb injury"],
        "General Surgery": ["Appendicitis", "Abdominal pain", "Gallstones"],
    }
    diagnoses = np.array(
        [rng.choice(diagnosis_by_specialty[value]) for value in specialty], dtype=object
    )

    severity = (
        0.7
        + (admission_methods == "Emergency") * 0.6
        + condition_counts * 0.18
        + np.isin(diagnoses, ["Sepsis", "Pneumonia", "Hip fracture"]) * 0.8
    )
    length_of_stay = np.clip(
        np.rint(rng.gamma(shape=1.5 + severity * 0.4, scale=1.5 + severity)).astype(
            int
        ),
        0,
        90,
    )
    long_stay_indexes = rng.choice(SPELL_COUNT, 90, replace=False)
    length_of_stay[long_stay_indexes] = np.clip(
        length_of_stay[long_stay_indexes] + rng.integers(15, 50, 90), 0, 90
    )
    discharge_dates = (
        admission_dates + pd.to_timedelta(length_of_stay, unit="D")
    ).clip(upper=pd.Timestamp("2025-12-31"))
    length_of_stay = (discharge_dates - admission_dates).dt.days.to_numpy()
    critical_care = np.where(
        rng.random(SPELL_COUNT) < np.clip(severity * 0.055, 0.02, 0.28),
        np.minimum(length_of_stay, rng.integers(1, 8, SPELL_COUNT)),
        0,
    )

    return pd.DataFrame(
        {
            "spell_id": [f"SPL{number:07d}" for number in range(1, SPELL_COUNT + 1)],
            "patient_id": spell_patients["patient_id"],
            "admission_date": admission_dates,
            "discharge_date": discharge_dates,
            "admission_method": admission_methods,
            "specialty": specialty,
            "hospital_site": rng.choice(
                ["Central Hospital", "North Hospital", "South Hospital"],
                SPELL_COUNT,
                p=[0.46, 0.29, 0.25],
            ),
            "primary_diagnosis": diagnoses,
            "length_of_stay_days": length_of_stay,
            "critical_care_days": critical_care,
            "discharge_destination": rng.choice(
                ["Home", "Community care", "Care home", "Other hospital"],
                SPELL_COUNT,
                p=[0.78, 0.10, 0.07, 0.05],
            ),
        }
    )


def _build_labs(
    rng: np.random.Generator, patients: pd.DataFrame, spells: pd.DataFrame
) -> pd.DataFrame:
    spell_weights = 1 + np.asarray(spells["length_of_stay_days"], dtype=float) * 0.08
    spell_indexes = rng.choice(
        spells.index,
        LAB_TEST_COUNT,
        replace=True,
        p=spell_weights / spell_weights.sum(),
    )
    selected_spells = spells.loc[spell_indexes].reset_index(drop=True)
    patient_lookup = patients.set_index("patient_id")
    dates_of_birth = selected_spells["patient_id"].map(patient_lookup["date_of_birth"])
    age_days: pd.Series = (selected_spells["admission_date"] - dates_of_birth).dt.days
    ages = np.clip(np.asarray(age_days, dtype=float) / 365.25, 0, None)

    stay_days = selected_spells["length_of_stay_days"].to_numpy()
    sample_offsets = np.array(
        [rng.integers(0, max(int(days), 0) + 1) for days in stay_days]
    )
    sample_dates = selected_spells["admission_date"] + pd.to_timedelta(
        sample_offsets, unit="D"
    )
    test_names = rng.choice(
        ["CRP", "Haemoglobin", "Sodium", "Potassium", "Creatinine", "WBC"],
        LAB_TEST_COUNT,
        p=[0.20, 0.19, 0.16, 0.14, 0.16, 0.15],
    )

    definitions = {
        "CRP": (0.0, 5.0, "mg/L"),
        "Haemoglobin": (120.0, 170.0, "g/L"),
        "Sodium": (135.0, 145.0, "mmol/L"),
        "Potassium": (3.5, 5.1, "mmol/L"),
        "Creatinine": (45.0, 110.0, "umol/L"),
        "WBC": (4.0, 11.0, "10^9/L"),
    }
    values = np.empty(LAB_TEST_COUNT, dtype=float)
    lower = np.empty(LAB_TEST_COUNT, dtype=float)
    upper = np.empty(LAB_TEST_COUNT, dtype=float)
    units = np.empty(LAB_TEST_COUNT, dtype=object)
    severity = (
        np.asarray(selected_spells["length_of_stay_days"], dtype=float) / 12
        + np.asarray(selected_spells["critical_care_days"], dtype=float) / 3
        + np.asarray(selected_spells["admission_method"].eq("Emergency"), dtype=float)
        * 0.6
    )

    for test_name, (reference_low, reference_high, unit) in definitions.items():
        mask = test_names == test_name
        count = int(mask.sum())
        lower[mask] = reference_low
        upper[mask] = reference_high
        units[mask] = unit
        if test_name == "CRP":
            values[mask] = rng.gamma(1.3 + severity[mask] * 0.35, 8.0, count)
        elif test_name == "Haemoglobin":
            values[mask] = rng.normal(
                142 - ages[mask] * 0.11 - severity[mask] * 2.5, 13, count
            )
        elif test_name == "Sodium":
            values[mask] = rng.normal(140 - severity[mask] * 0.35, 3.2, count)
        elif test_name == "Potassium":
            values[mask] = rng.normal(4.25 + severity[mask] * 0.04, 0.48, count)
        elif test_name == "Creatinine":
            values[mask] = (
                rng.gamma(3.0, 17.0, count) + ages[mask] * 0.48 + severity[mask] * 5
            )
        else:
            values[mask] = rng.gamma(3.1 + severity[mask] * 0.12, 2.0, count)

    values = np.round(np.clip(values, 0.1, None), 1)
    abnormal_flags = np.where(
        values < lower, "Low", np.where(values > upper, "High", "Normal")
    )

    return pd.DataFrame(
        {
            "lab_test_id": [
                f"LAB{number:08d}" for number in range(1, LAB_TEST_COUNT + 1)
            ],
            "spell_id": selected_spells["spell_id"],
            "patient_id": selected_spells["patient_id"],
            "sample_date": sample_dates,
            "test_name": test_names,
            "result_value": values,
            "result_unit": units,
            "reference_low": lower,
            "reference_high": upper,
            "abnormal_flag": abnormal_flags,
        }
    )


def _validate(
    patients: pd.DataFrame, spells: pd.DataFrame, lab_tests: pd.DataFrame
) -> None:
    assert len(patients) == PATIENT_COUNT
    assert len(spells) == SPELL_COUNT
    assert len(lab_tests) == LAB_TEST_COUNT
    assert patients["patient_id"].is_unique
    assert spells["spell_id"].is_unique
    assert lab_tests["lab_test_id"].is_unique
    assert not patients.isna().any().any()
    assert not spells.isna().any().any()
    assert not lab_tests.isna().any().any()
    assert set(spells["patient_id"]).issubset(set(patients["patient_id"]))
    assert set(lab_tests["spell_id"]).issubset(set(spells["spell_id"]))
    assert set(lab_tests["patient_id"]).issubset(set(patients["patient_id"]))
    assert (spells["discharge_date"] >= spells["admission_date"]).all()
    assert spells["discharge_date"].max() <= pd.Timestamp("2025-12-31")
    assert (spells["length_of_stay_days"] >= 0).all()
    spell_lookup = spells.set_index("spell_id")
    matched_admissions = lab_tests["spell_id"].map(spell_lookup["admission_date"])
    matched_discharges = lab_tests["spell_id"].map(spell_lookup["discharge_date"])
    matched_patients = lab_tests["spell_id"].map(spell_lookup["patient_id"])
    assert (lab_tests["patient_id"] == matched_patients).all()
    assert (lab_tests["sample_date"] >= matched_admissions).all()
    assert (lab_tests["sample_date"] <= matched_discharges).all()


def generate_demo_data(
    output_dir: str | Path | None = None, seed: int = SEED
) -> ResultList:
    """Generate synthetic demo tables in memory.

    Pass ``output_dir`` to additionally save the generated tables as CSV files.
    """
    rng = np.random.default_rng(seed)
    patients = _build_patients(rng)
    spells = _build_spells(rng, patients)
    lab_tests = _build_labs(rng, patients, spells)
    _validate(patients, spells, lab_tests)

    datasets = {
        "patients": patients,
        "inpatient_spells": spells,
        "lab_tests": lab_tests,
    }
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        for name, dataframe in datasets.items():
            dataframe.to_csv(
                directory / f"{name}.csv", index=False, date_format="%Y-%m-%d"
            )

    return ResultList(
        [Result(dataframe, df_name=name) for name, dataframe in datasets.items()]
    )
