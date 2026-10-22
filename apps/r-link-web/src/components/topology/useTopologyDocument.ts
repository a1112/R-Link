import { useCallback, useRef, useState } from 'react';
import { documentKey, emptyDocument, readDocument, type CanvasDocument } from './interaction';

export function useTopologyDocument(scope: string) {
  const key = documentKey(scope);
  const [document, setDocument] = useState(() => {
    try { return readDocument(localStorage.getItem(key)); } catch { return emptyDocument(); }
  });
  const current = useRef(document);
  const past = useRef<CanvasDocument[]>([]), future = useRef<CanvasDocument[]>([]);
  const [saveError, setSaveError] = useState(false);
  const publish = useCallback((next: CanvasDocument) => {
    current.current = next; setDocument(next);
    try { localStorage.setItem(key, JSON.stringify(next)); setSaveError(false); } catch { setSaveError(true); }
  }, [key]);
  const commit = useCallback((next: CanvasDocument) => {
    if (JSON.stringify(current.current) === JSON.stringify(next)) return;
    past.current = [...past.current.slice(-49), current.current]; future.current = []; publish(next);
  }, [publish]);
  const undo = useCallback(() => {
    const next = past.current.pop();
    if (next) { future.current.push(current.current); publish(next); }
  }, [publish]);
  const redo = useCallback(() => {
    const next = future.current.pop();
    if (next) { past.current.push(current.current); publish(next); }
  }, [publish]);
  return { document, commit, undo, redo, canUndo: past.current.length > 0, canRedo: future.current.length > 0, saveError };
}
