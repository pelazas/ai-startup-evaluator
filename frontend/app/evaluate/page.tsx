"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { IdeaInputForm } from "@/components/evaluation/IdeaInputForm";
import { ProgressIndicator } from "@/components/evaluation/ProgressIndicator";
import { useAuth } from "@/contexts/auth-context";
import {
  EvaluationCreatePayload,
  EvaluationResultData,
  streamEvaluation,
  upsertStoredEvaluation,
} from "@/lib/evaluations";

export default function EvaluatePage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();
  const [status, setStatus] = useState<"checking" | "ready" | "error">("checking");
  const [running, setRunning] = useState(false);
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [lastPayload, setLastPayload] = useState<EvaluationCreatePayload | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }

    if (!user) {
      setStatus("checking");
      return;
    }

    if (!user.has_profile) {
      router.replace("/profile/setup");
      return;
    }
    setStatus("ready");
  }, [isAuthenticated, router, user]);

  if (status === "checking") {
    return (
      <main>
        <h1>New Evaluation</h1>
        <p>Checking profile status...</p>
      </main>
    );
  }

  if (status === "error") {
    return (
      <main>
        <h1>New Evaluation</h1>
        <p className="form-error">Unable to verify your account. Please log in again.</p>
      </main>
    );
  }

  async function runEvaluation(payload: EvaluationCreatePayload) {
    setRunning(true);
    setCompletedNodes([]);
    setActiveNode("intake");
    setProgressError(null);
    setLastPayload(payload);

    const finalResult = await new Promise<EvaluationResultData | null>((resolve) => {
      let resolved = false;
      void streamEvaluation(payload, (event) => {
        if (event.type === "progress") {
          setActiveNode(event.node);
          setCompletedNodes((prev) => (prev.includes(event.node) ? prev : [...prev, event.node]));
        } else if (event.type === "error") {
          setProgressError(event.message);
        } else if (event.type === "result") {
          resolved = true;
          resolve(event.data);
        }
      }).then(() => {
        if (!resolved) {
          resolve(null);
        }
      });
    });

    if (finalResult === null) {
      setProgressError("Evaluation finished without result payload.");
      setRunning(false);
      return;
    }

    const record = {
      id: finalResult.evaluation_id,
      created_at: new Date().toISOString(),
      status: finalResult.status,
      idea_input: payload,
      result: finalResult,
    };
    upsertStoredEvaluation(record);
    router.push(`/evaluations/${finalResult.evaluation_id}`);
  }

  return (
    <main>
      <h1>New Evaluation</h1>
      {!running ? (
        <>
          <p>Describe your startup idea to begin an evidence-grounded evaluation.</p>
          <IdeaInputForm onSubmit={runEvaluation} />
        </>
      ) : (
        <>
          <ProgressIndicator completedNodes={completedNodes} activeNode={activeNode} errorMessage={progressError} />
          {progressError ? (
            <button
              type="button"
              onClick={() => {
                if (lastPayload) {
                  void runEvaluation(lastPayload);
                }
              }}
            >
              Try Again
            </button>
          ) : null}
        </>
      )}
    </main>
  );
}
