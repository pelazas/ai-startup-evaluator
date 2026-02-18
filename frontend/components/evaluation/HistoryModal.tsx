"use client";

import { useEffect, useMemo, useState } from "react";

import { EvaluationResultData, StoredEvaluation, fetchEvaluationsFiltered } from "@/lib/evaluations";

type HistoryModalProps = {
  items: StoredEvaluation[];
  onClose: () => void;
  onSelect: (id: string) => void;
};

export function HistoryModal({ items, onClose, onSelect }: HistoryModalProps) {
  const [folderFilter, setFolderFilter] = useState<string>("");
  const [tagFilter, setTagFilter] = useState<string>("");
  const [aiQuery, setAiQuery] = useState<string>("");
  const [remoteItems, setRemoteItems] = useState<StoredEvaluation[] | null>(null);
  const [remoteLoading, setRemoteLoading] = useState(false);

  const localById = useMemo(() => {
    const map = new Map<string, StoredEvaluation>();
    for (const item of items) {
      map.set(item.id, item);
    }
    return map;
  }, [items]);

  const folders = useMemo(() => {
    const set = new Set<string>();
    for (const item of items) {
      const folder = item.result.idea_folder?.trim();
      if (folder) {
        set.add(folder);
      }
    }
    return Array.from(set).sort();
  }, [items]);

  const tags = useMemo(() => {
    const set = new Set<string>();
    for (const item of items) {
      for (const tag of item.result.idea_tags ?? []) {
        const normalized = tag.trim().toLowerCase();
        if (normalized) {
          set.add(normalized);
        }
      }
    }
    return Array.from(set).sort();
  }, [items]);

  function toStoredFromResult(result: EvaluationResultData): StoredEvaluation {
    const existing = localById.get(result.evaluation_id);
    if (existing) {
      return { ...existing, result: { ...existing.result, ...result } };
    }
    return {
      id: result.evaluation_id,
      created_at: result.created_at ?? new Date().toISOString(),
      status: result.status,
      idea_input: { idea_description: result.idea_title ?? "Loaded from evaluation history" },
      result,
    };
  }

  useEffect(() => {
    const shouldUseServerAi = aiQuery.trim().length > 1;
    if (!shouldUseServerAi) {
      setRemoteItems(null);
      setRemoteLoading(false);
      return;
    }
    let cancelled = false;
    setRemoteLoading(true);
    const timer = setTimeout(async () => {
      const data = await fetchEvaluationsFiltered({
        limit: 100,
        folder: folderFilter || undefined,
        tag: tagFilter || undefined,
        q: aiQuery,
        ai_filter: true,
      });
      if (cancelled) {
        return;
      }
      if (data) {
        setRemoteItems(data.map((entry) => toStoredFromResult(entry)));
      } else {
        setRemoteItems([]);
      }
      setRemoteLoading(false);
    }, 280);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [aiQuery, folderFilter, tagFilter, localById]);

  const filteredItems = useMemo(() => {
    const source = remoteItems ?? items;
    const queryTokens = aiQuery
      .toLowerCase()
      .split(/[\s,]+/)
      .map((value) => value.trim())
      .filter(Boolean);

    return source.filter((item) => {
      const rowFolder = (item.result.idea_folder ?? "").toLowerCase();
      const rowTags = (item.result.idea_tags ?? []).map((tag) => tag.toLowerCase());

      if (folderFilter && rowFolder !== folderFilter.toLowerCase()) {
        return false;
      }
      if (tagFilter && !rowTags.includes(tagFilter.toLowerCase())) {
        return false;
      }
      if (queryTokens.length) {
        const haystack = [rowFolder, ...rowTags, item.idea_input.idea_description.toLowerCase()].join(" ");
        if (!queryTokens.every((token) => haystack.includes(token))) {
          return false;
        }
      }
      return true;
    });
  }, [aiQuery, folderFilter, items, remoteItems, tagFilter]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>Evaluation History</h3>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="history-filters">
          <label>
            Folder
            <select value={folderFilter} onChange={(event) => setFolderFilter(event.target.value)}>
              <option value="">All folders</option>
              {folders.map((folder) => (
                <option key={folder} value={folder}>
                  {folder}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tag
            <select value={tagFilter} onChange={(event) => setTagFilter(event.target.value)}>
              <option value="">All tags</option>
              {tags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
          </label>
          <label>
            AI filter query
            <input
              type="text"
              placeholder="e.g. b2b ai agent fintech"
              value={aiQuery}
              onChange={(event) => setAiQuery(event.target.value)}
            />
          </label>
        </div>
        <div className="modal-list">
          {remoteLoading ? <p className="form-note">Applying AI filter...</p> : null}
          {filteredItems.map((item) => (
            <button key={item.id} type="button" className="history-item" onClick={() => onSelect(item.id)}>
              <div className="history-title">{item.idea_input.idea_description.slice(0, 80)}</div>
              <div className="history-tags-row">
                {item.result.idea_folder ? <span className="history-folder-chip">{item.result.idea_folder}</span> : null}
                {(item.result.idea_tags ?? []).slice(0, 4).map((tag) => (
                  <span key={`${item.id}-${tag}`} className="history-tag-chip">
                    {tag}
                  </span>
                ))}
              </div>
              <div className="history-meta">
                <span>{item.result.verdict ?? "N/A"}</span>
                <span>{item.result.overall_score ?? "N/A"}</span>
                <span>{new Date(item.created_at).toLocaleString()}</span>
              </div>
            </button>
          ))}
          {!filteredItems.length ? <p className="form-note">No evaluations match the selected filters.</p> : null}
        </div>
      </div>
    </div>
  );
}
