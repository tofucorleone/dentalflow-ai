"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Patient360 } from "@/lib/patient360";

type Props = {
  patientId: string;
  documents: Patient360["documents"];
};

const DOCUMENT_TYPES = [
  { value: "radio", label: "Radio" },
  { value: "photo", label: "Photo" },
  { value: "ordonnance", label: "Ordonnance" },
  { value: "devis", label: "Devis" },
  { value: "other", label: "Autre" },
];

export function PatientDocuments({
  patientId,
  documents,
}: Props) {
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [documentType, setDocumentType] = useState("other");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [analysisResult, setAnalysisResult] = useState<{
    documentId: string;
    text: string;
    page_count: number;
    character_count: number;
    requires_ocr: boolean;
  } | null>(null);

  const [isEditingAnalysis, setIsEditingAnalysis] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);

  const router = useRouter();

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!selectedFile) {
      return;
    }

    const formData = new FormData();
    formData.append("document_type", documentType);
    formData.append("file", selectedFile);

    const response = await fetch(
      `/api/patients/${patientId}/documents`,
      {
        method: "POST",
        body: formData,
      },
    );

    if (!response.ok) {
      alert("Échec de l'upload.");
      return;
    }

    setSelectedFile(null);
    setDocumentType("other");
    setShowUploadForm(false);

    router.refresh();
  }

  async function handleDelete(documentId: string) {
    const response = await fetch(
      `/api/patients/${patientId}/documents/${documentId}`,
      {
        method: "DELETE",
      },
    );

    if (!response.ok) {
      alert("Impossible de supprimer le document.");
      return;
    }

    router.refresh();
  }

  async function handleAnalyze(documentId: string) {
    const response = await fetch(
      `/api/patients/${patientId}/documents/${documentId}/extract`,
      {
        method: "POST",
      },
    );

    const body = await response.json();

    if (!response.ok) {
      alert(
        typeof body.detail === "string"
          ? body.detail
          : "Impossible d'analyser le document.",
      );
      return;
    }

    setAnalysisResult({
      documentId,
      ...body,
    });
  }

  async function handleSummarize() {
    if (!analysisResult) {
      return;
    }

    setIsSummarizing(true);
    setSummary(null);

    try {
      const response = await fetch(
        `/api/patients/${patientId}/documents/${analysisResult.documentId}/summary`,
        {
          method: "POST",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        alert(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de générer le résumé IA.",
        );
        return;
      }

      setSummary(body.summary);
    } finally {
      setIsSummarizing(false);
    }
  }


  async function handleSaveAnalysis() {
    if (!analysisResult) {
      return;
    }

    const response = await fetch(
      `/api/patients/${patientId}/documents/${analysisResult.documentId}/extracted-text`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: analysisResult.text,
        }),
      },
    );

    const body = await response.json();

    if (!response.ok) {
      alert(
        typeof body.detail === "string"
          ? body.detail
          : "Impossible d'enregistrer le texte.",
      );
      return;
    }

    setIsEditingAnalysis(false);
  }


  return (
    <article className="panel">
      <p className="eyebrow">Documents</p>

        <div className="document-header">
        <h2>Dossier administratif</h2>

        <button
          type="button"
          onClick={() =>
            setShowUploadForm((value) => !value)
          }
        >
          {showUploadForm
            ? "Annuler"
            : "Ajouter un document"}
        </button>
      </div>

      {showUploadForm && (
        <form
  onSubmit={handleSubmit}
  className="document-upload-form"
>
          <div>
            <label htmlFor="document-type">
              Type de document
            </label>

            <select
              id="document-type"
              value={documentType}
              onChange={(event) =>
                setDocumentType(event.target.value)
              }
            >
              {DOCUMENT_TYPES.map((type) => (
                <option
                  key={type.value}
                  value={type.value}
                >
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="document-file">
              Fichier
            </label>

            <input
              id="document-file"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.webp"
              onChange={(event) =>
                setSelectedFile(
                  event.target.files?.[0] ?? null,
                )
              }
            />

            {selectedFile && (
              <small>
                Fichier sélectionné : {selectedFile.name}
              </small>
            )}
          </div>

          <button
            type="submit"
            disabled={!selectedFile}
          >
            Téléverser
          </button>
        </form>
      )}

      {documents.length === 0 ? (
        <p className="empty-state">
          Aucun document enregistré.
        </p>
      ) : (
        <div className="document-list">
          {documents.map((document) => (
            <div
                key={document.id}
                className="document-item"
            >
              <a
                href={`/api/patients/${patientId}/documents/${document.id}`}
                target="_blank"
                rel="noreferrer"
                className="document-info"
              >
                <strong>
                  {document.original_filename ??
                    document.filename}
                </strong>

                <span>{document.document_type}</span>
              </a>

              <button
                type="button"
                className="document-icon-button"
                onClick={() =>
                  handleAnalyze(document.id)
                }
                title="Analyser"
              >
                🤖
              </button>

              <button
                type="button"
                onClick={() =>
                  handleDelete(document.id)
                }
                title="Supprimer"
              >
                🗑
              </button>
            </div>
          ))}
        </div>
      )}
      {analysisResult && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Texte extrait du document"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "grid",
            placeItems: "center",
            padding: "24px",
            background: "rgba(15, 23, 42, 0.55)",
          }}
        >
          <div
            style={{
              width: "min(900px, 100%)",
              maxHeight: "85vh",
              overflow: "auto",
              padding: "24px",
              borderRadius: "16px",
              background: "white",
              boxShadow: "0 24px 70px rgba(15, 23, 42, 0.25)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "16px",
                marginBottom: "16px",
              }}
            >
              <div>
                <p className="eyebrow">Analyse documentaire</p>
                <h2>Texte extrait</h2>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "8px",
                  alignItems: "center",
                }}
              >
                {isEditingAnalysis ? (
                  <button
                    type="button"
                    onClick={handleSaveAnalysis}
                  >
                    Enregistrer
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsEditingAnalysis(true)}
                  >
                    Modifier
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    setIsEditingAnalysis(false);
                    setAnalysisResult(null);
                  }}
                >
                  Fermer
                </button>
              </div>
            </div>

            <p>
              {analysisResult.page_count} page(s) ·{" "}
              {analysisResult.character_count} caractère(s)
            </p>

            <button
              type="button"
              onClick={handleSummarize}
              disabled={isSummarizing}
              style={{
                marginBottom: "16px",
              }}
            >
              {isSummarizing
                ? "Génération du résumé…"
                : "Résumer avec l'IA"}
            </button>

            {summary && (
              <section
                style={{
                  marginBottom: "16px",
                  padding: "16px",
                  border: "1px solid #dbe7ec",
                  borderRadius: "12px",
                  background: "#f1f8fa",
                }}
              >
                <p className="eyebrow">Résumé IA</p>

                <div
                  style={{
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.6,
                  }}
                >
                  {summary}
                </div>
              </section>
            )}

            {analysisResult.requires_ocr && (
              <p>
                Ce document nécessite un traitement OCR.
              </p>
            )}

            {isEditingAnalysis ? (
              <textarea
                value={analysisResult.text}
                onChange={(event) =>
                  setAnalysisResult({
                    ...analysisResult,
                    text: event.target.value,
                    character_count: event.target.value.length,
                  })
                }
                style={{
                  width: "100%",
                  minHeight: "500px",
                  padding: "16px",
                  resize: "vertical",
                  border: "1px solid #e5eaf1",
                  borderRadius: "12px",
                  background: "white",
                  font: "inherit",
                  lineHeight: 1.6,
                }}
              />
            ) : (
              <pre
                style={{
                  margin: 0,
                  padding: "16px",
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  border: "1px solid #e5eaf1",
                  borderRadius: "12px",
                  background: "#f8fafc",
                  fontFamily: "inherit",
                  lineHeight: 1.6,
                }}
              >
                {analysisResult.text ||
                  "Aucun texte n'a pu être extrait."}
              </pre>
            )}
          </div>
        </div>
      )}

    </article>
  );
}
