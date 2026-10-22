export type Point = { x: number; y: number };
export type Camera = Point & { zoom: number };
export type Annotation = { name: string; note: string };
export type CanvasDocument = { positions: Record<string, Point>; annotations: Record<string, Annotation> };
export const emptyDocument = (): CanvasDocument => ({ positions: {}, annotations: {} });
export const documentKey = (scope: string) => `r-link-topology:v1:${scope}`;
export const clampZoom = (value: number) => Math.max(.1, Math.min(3, value));
export const toWorld = (point: Point, camera: Camera): Point => ({ x: (point.x - camera.x) / camera.zoom, y: (point.y - camera.y) / camera.zoom });
export function zoomAt(camera: Camera, anchor: Point, value: number): Camera {
  const world = toWorld(anchor, camera), zoom = clampZoom(value);
  return { zoom, x: anchor.x - world.x * zoom, y: anchor.y - world.y * zoom };
}
export function fitCamera(points: Point[], size: { width: number; height: number }): Camera {
  if (!points.length) return { x: size.width / 2, y: size.height / 2, zoom: 1 };
  const left = Math.min(...points.map(p => p.x)) - 106, right = Math.max(...points.map(p => p.x)) + 106;
  const top = Math.min(...points.map(p => p.y)) - 56, bottom = Math.max(...points.map(p => p.y)) + 56;
  const zoom = clampZoom(Math.min(1, (size.width - 48) / (right - left), (size.height - 48) / (bottom - top)));
  return { zoom, x: (size.width - (left + right) * zoom) / 2, y: (size.height - (top + bottom) * zoom) / 2 };
}
export function insideBox(point: Point, a: Point, b: Point) {
  return point.x + 106 >= Math.min(a.x, b.x) && point.x - 106 <= Math.max(a.x, b.x)
    && point.y + 56 >= Math.min(a.y, b.y) && point.y - 56 <= Math.max(a.y, b.y);
}
export function readDocument(raw: string | null): CanvasDocument {
  const result = emptyDocument();
  try {
    const data = JSON.parse(raw || '{}');
    for (const [id, value] of Object.entries(data.positions ?? {}).slice(0, 10000)) {
      const point = value as Point;
      if (id !== '__proto__' && point && Number.isFinite(point.x) && Number.isFinite(point.y) && Math.abs(point.x) <= 1e6 && Math.abs(point.y) <= 1e6) result.positions[id] = { x: point.x, y: point.y };
    }
    for (const [id, value] of Object.entries(data.annotations ?? {}).slice(0, 10000)) {
      const note = value as Annotation;
      if (id !== '__proto__' && note && typeof note.name === 'string' && typeof note.note === 'string') result.annotations[id] = { name: note.name.slice(0, 80), note: note.note.slice(0, 1000) };
    }
  } catch { /* Damaged local preferences must not stop device access. */ }
  return result;
}
