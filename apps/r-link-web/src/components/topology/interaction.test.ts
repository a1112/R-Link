import { expect, it } from 'vitest';
import { zoomAt, toWorld, fitCamera, insideBox, readDocument, documentKey } from './interaction';

it('zooms around the cursor without moving the world point below it', () => {
  const camera = { x: -120, y: 40, zoom: .8 }, cursor = { x: 217, y: 119 };
  const next = zoomAt(camera, cursor, 2);
  expect(toWorld(cursor, next)).toEqual(toWorld(cursor, camera));
  expect(zoomAt(camera, cursor, 99).zoom).toBe(3);
  expect(zoomAt(camera, cursor, .001).zoom).toBe(.1);
});
it('fits translated and negative node positions in the actual viewport', () => {
  const camera = fitCamera([{ x: -900, y: 900 }, { x: 2100, y: 200 }], { width: 800, height: 500 });
  for (const point of [{x:-1006,y:956},{x:2206,y:144}]) {
    expect(point.x * camera.zoom + camera.x).toBeGreaterThanOrEqual(20);
    expect(point.x * camera.zoom + camera.x).toBeLessThanOrEqual(780);
    expect(point.y * camera.zoom + camera.y).toBeGreaterThanOrEqual(20);
    expect(point.y * camera.zoom + camera.y).toBeLessThanOrEqual(480);
  }
});
it('selects cards intersecting a rectangle in either drag direction', () => {
  expect(insideBox({x:200,y:200},{x:110,y:170},{x:50,y:150})).toBe(true);
  expect(insideBox({x:400,y:400},{x:110,y:170},{x:50,y:150})).toBe(false);
});
it('rejects corrupted persistence and separates service scopes', () => {
  expect(readDocument('{bad')).toEqual({positions:{}, annotations:{}});
  const parsed = readDocument(JSON.stringify({positions:{ok:{x:12,y:-3},bad:{x:'bad',y:1}},annotations:{ok:{name:'Home',note:'Local'},bad:{name:{}}}}));
  expect(parsed.positions).toEqual({ok:{x:12,y:-3}});
  expect(parsed.annotations).toEqual({ok:{name:'Home',note:'Local'}});
  expect(documentKey('https://a.example')).not.toBe(documentKey('https://b.example'));
});
