"use client";

import { StoredEvaluation } from "@/lib/evaluations";

type HistoryModalProps = {
  items: StoredEvaluation[];
  onClose: () => void;
  onSelect: (id: string) => void;
};

export function HistoryModal({ items, onClose, onSelect }: HistoryModalProps) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>Evaluation History</h3>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-list">
          {items.map((item) => (
            <button key={item.id} type="button" className="history-item" onClick={() => onSelect(item.id)}>
              <div className="history-title">{item.idea_input.idea_description.slice(0, 80)}</div>
              <div className="history-meta">
                <span>{item.result.verdict ?? "N/A"}</span>
                <span>{item.result.overall_score ?? "N/A"}</span>
                <span>{new Date(item.created_at).toLocaleString()}</span>
              </div>
            </button>
          ))}
          {!items.length ? <p className="form-note">No evaluations yet.</p> : null}
        </div>
      </div>
    </div>
  );
}

