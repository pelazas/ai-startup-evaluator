"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { ResultsDisplay } from "@/components/evaluation/ResultsDisplay";
import {
  fetchEvaluationById,
  getStoredEvaluationById,
  loadStoredEvaluations,
  upsertStoredEvaluation,
  type StoredEvaluation,
} from "@/lib/evaluations";
import { useAuth } from "@/contexts/auth-context";

export default function EvaluationResultPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [evaluation, setEvaluation] = useState<StoredEvaluation | null>(null);
  const [history, setHistory] = useState<StoredEvaluation[]>([]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!user?.has_profile) {
      router.replace("/profile/setup");
      return;
    }

    let mounted = true;
    async function run() {
      const local = getStoredEvaluationById(id);
      if (local && mounted) {
        setEvaluation(local);
      }

      const remote = await fetchEvaluationById(id);
      if (remote && mounted) {
        const normalized: StoredEvaluation = {
          id: remote.evaluation_id,
          created_at: new Date().toISOString(),
          status: remote.status,
          idea_input: local?.idea_input ?? { idea_description: "Loaded from server" },
          result: remote,
        };
        upsertStoredEvaluation(normalized);
        setEvaluation(normalized);
      }

      if (mounted) {
        setHistory(loadStoredEvaluations());
        setLoading(false);
      }
    }
    void run();

    return () => {
      mounted = false;
    };
  }, [id, isAuthenticated, router, user?.has_profile]);

  if (loading) {
    return (
      <main>
        <h1>Evaluation Results</h1>
        <p>Loading...</p>
      </main>
    );
  }

  if (!evaluation) {
    return (
      <main>
        <h1>Evaluation Results</h1>
        <p className="form-error">Result not found.</p>
      </main>
    );
  }

  return <ResultsDisplay evaluation={evaluation} history={history} />;
}

