"use client";

import { Search, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PatientCreateForm } from "@/components/patient-create-form";
import { PatientListActions } from "@/components/patient-list-actions";

type Patient = {
  id: string;
  full_name: string | null;
  phone: string;
  email: string | null;
  administrative_notes: string | null;
};

type PatientDirectoryProps = {
  patients: Patient[];
};

function normalizeSearchValue(
  value: string | null | undefined,
) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("fr")
    .trim();
}

function normalizePhoneDigits(
  value: string | null | undefined,
) {
  return (value ?? "").replace(/\D/g, "");
}

function getLocalPhoneVariants(
  value: string | null | undefined,
) {
  const rawValue = (value ?? "").trim();
  let digits = normalizePhoneDigits(rawValue);

  const variants = new Set<string>();

  if (!digits) {
    return variants;
  }

  variants.add(digits);

  if (digits.startsWith("00")) {
    digits = digits.slice(2);
    variants.add(digits);
  }

  const countryCodes = [
    "213",
    "212",
    "216",
    "33",
  ];

  for (const countryCode of countryCodes) {
    if (!digits.startsWith(countryCode)) {
      continue;
    }

    const nationalNumber = digits.slice(
      countryCode.length,
    );

    if (nationalNumber) {
      variants.add(nationalNumber);
      variants.add(`0${nationalNumber}`);
    }

    break;
  }

  if (digits.startsWith("0")) {
    variants.add(digits.slice(1));
  } else {
    variants.add(`0${digits}`);
  }

  return variants;
}

function phoneMatchesQuery(
  phone: string | null | undefined,
  query: string,
) {
  const phoneVariants = getLocalPhoneVariants(phone);
  const queryVariants = getLocalPhoneVariants(query);

  return [...phoneVariants].some((phoneVariant) =>
    [...queryVariants].some(
      (queryVariant) =>
        queryVariant.length > 0
        && phoneVariant.startsWith(queryVariant),
    ),
  );
}

export function PatientDirectory({
  patients,
}: PatientDirectoryProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const normalizedQuery = normalizeSearchValue(searchQuery);

  const filteredPatients = useMemo(() => {
    const trimmedQuery = searchQuery.trim();

    if (!trimmedQuery) {
      return patients;
    }

    const isPhoneQuery =
      /^[+\d\s().-]+$/.test(trimmedQuery)
      && normalizePhoneDigits(trimmedQuery).length > 0;

    return patients.filter((patient) => {
      if (isPhoneQuery) {
        return phoneMatchesQuery(
          patient.phone,
          trimmedQuery,
        );
      }

      const searchableContent = [
        patient.full_name,
        patient.email,
      ]
        .map(normalizeSearchValue)
        .join(" ");

      return searchableContent.includes(
        normalizedQuery,
      );
    });
  }, [normalizedQuery, patients, searchQuery]);

  return (
    <section className="patient-directory">
      <div className="patient-directory-toolbar">
        <div className="patient-search-field">
          <Search
            aria-hidden="true"
            className="patient-search-icon"
            size={21}
          />

          <input
            type="search"
            value={searchQuery}
            onChange={(event) =>
              setSearchQuery(event.target.value)
            }
            placeholder="Rechercher un patient..."
            aria-label="Rechercher un patient"
            autoComplete="off"
          />

          {searchQuery ? (
            <button
              className="patient-search-clear"
              type="button"
              onClick={() => setSearchQuery("")}
              aria-label="Effacer la recherche"
              title="Effacer la recherche"
            >
              <X size={17} />
            </button>
          ) : null}
        </div>

        <PatientCreateForm />
      </div>

      <div className="patient-directory-summary">
        <span>
          {filteredPatients.length} patient
          {filteredPatients.length > 1 ? "s" : ""}
        </span>

        {normalizedQuery ? (
          <span>
            Résultat{filteredPatients.length > 1 ? "s" : ""} pour
            « {searchQuery.trim()} »
          </span>
        ) : null}
      </div>

      {filteredPatients.length > 0 ? (
        <section className="card-grid patient-results-grid">
          {filteredPatients.map((patient) => (
            <article
              className="person-card patient-list-card"
              key={patient.id}
            >
              <Link
                className="patient-card-main"
                href={`/patients/${patient.id}`}
              >
                <div className="avatar">
                  {(patient.full_name ?? "P")
                    .slice(0, 1)
                    .toUpperCase()}
                </div>

                <div>
                  <strong>
                    {patient.full_name ?? "Patient sans nom"}
                  </strong>

                  <p>{patient.phone}</p>

                  <span>
                    {patient.email ?? "Aucun e-mail"}
                  </span>
                </div>
              </Link>

              <div className="patient-card-actions">
                <PatientListActions patient={patient} />
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="patient-search-empty">
          <span className="patient-search-empty-icon">
            <Search size={25} />
          </span>

          <div>
            <h2>Aucun patient trouvé</h2>

            <p>
              Essayez avec un autre nom, numéro de téléphone
              ou une autre adresse e-mail.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setSearchQuery("")}
          >
            Effacer la recherche
          </button>
        </section>
      )}
    </section>
  );
}
