import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { TopologyCanvas } from './TopologyCanvas';
import { makeNodes, layoutNodes } from './model';
import { useTopologyDocument } from './useTopologyDocument';
import { documentKey } from './interaction';
import type { Device } from '../../api/devices';
const devices = ['a','b'].map((id): Device => ({id,name:id,host:'localhost',port:22,username:'',revision:1,status:'unchecked',checked_at:null,latency_ms:null}));
const nodes = makeNodes(devices,null), layout = layoutNodes(nodes);
function Harness({scope='test', edit=vi.fn()}: {scope?:string;edit?:()=>void}) {
  const [selection,setSelection] = useState<string[]>([]);
  const store = useTopologyDocument(scope);
  return <TopologyCanvas layout={layout} visibleIds={nodes.map(n=>n.id)} selection={selection} onSelection={setSelection} store={store} serverName="Hub" onEditDevice={edit} />;
}
beforeEach(() => {
  localStorage.clear();
  class Pointer extends MouseEvent { pointerId: number; pointerType: string; constructor(type:string, init:PointerEventInit) { super(type,init); this.pointerId=init.pointerId ?? 1; this.pointerType=init.pointerType ?? 'mouse'; } }
  vi.stubGlobal('PointerEvent',Pointer);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const canvas = () => screen.getByLabelText('拓扑画布');
const drag = (target:Element, from=[100,100], to=[180,140]) => {
  fireEvent.pointerDown(target,{pointerId:1,button:0,clientX:from[0],clientY:from[1]});
  fireEvent.pointerMove(canvas(),{pointerId:1,clientX:to[0],clientY:to[1]});
  fireEvent.pointerUp(canvas(),{pointerId:1,clientX:to[0],clientY:to[1]});
};
it('freely pans even when the graph fits, and anchors wheel zoom', () => {
  render(<Harness />);
  const stage=screen.getByTestId('topology-stage'), before=stage.style.transform;
  drag(canvas()); expect(stage.style.transform).not.toBe(before);
  const zoom=screen.getByLabelText('缩放比例').textContent;
  fireEvent.wheel(canvas(),{deltaY:-240,clientX:200,clientY:150});
  expect(screen.getByLabelText('缩放比例').textContent).not.toBe(zoom);
});
it('moves a selected group in world coordinates and supports undo/redo and persistence', () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole('button',{name:'查看设备：a'}));
  fireEvent.click(screen.getByRole('button',{name:'查看设备：b'}),{shiftKey:true});
  expect(screen.getByText('已选 2 台')).toBeTruthy();
  drag(screen.getByRole('button',{name:'查看设备：a'}));
  const saved=JSON.parse(localStorage.getItem(documentKey('test'))!);
  expect(Object.keys(saved.positions)).toHaveLength(2);
  const dx=saved.positions['device:a'].x-layout.nodes[0].x;
  expect(dx).not.toBe(0);
  expect(saved.positions['device:b'].x-layout.nodes[1].x).toBeCloseTo(dx);
  fireEvent.click(screen.getByRole('button',{name:'撤销'}));
  expect(JSON.parse(localStorage.getItem(documentKey('test'))!).positions).toEqual({});
  fireEvent.click(screen.getByRole('button',{name:'重做'}));
  expect(JSON.parse(localStorage.getItem(documentKey('test'))!).positions).toEqual(saved.positions);
  cleanup();render(<Harness />);
  expect(screen.getByRole('button',{name:'查看设备：a'}).style.left).toBe(`${saved.positions['device:a'].x}px`);
});
it('cancels a drag without saving and keeps keyboard selection/editing available', () => {
  const edit=vi.fn();render(<Harness edit={edit} />);
  const node=screen.getByRole('button',{name:'查看设备：a'});
  fireEvent.pointerDown(node,{pointerId:1,button:0,clientX:100,clientY:100});
  fireEvent.pointerMove(canvas(),{pointerId:1,clientX:200,clientY:180});
  fireEvent.pointerCancel(canvas(),{pointerId:1});
  expect(localStorage.getItem(documentKey('test'))).toBeNull();
  fireEvent.click(node); fireEvent.keyDown(canvas(),{key:'F2'});
  expect(screen.getByRole('dialog',{name:'编辑本机标注'})).toBeTruthy();
  fireEvent.change(screen.getByLabelText('显示名称'),{target:{value:'Office'}});
  fireEvent.click(screen.getByRole('button',{name:'保存标注'}));
  expect(screen.getByRole('button',{name:'查看设备：Office'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'编辑所选设备'}));expect(edit).toHaveBeenCalledWith(devices[0]);
  fireEvent.keyDown(canvas(),{key:'Escape'});expect(screen.queryByText('已选 1 台')).toBeNull();
});
it('box-selects visible cards and supports two-finger pinch without moving nodes', () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole('button',{name:'框选工具'}));
  drag(canvas(),[0,0],[960,640]);expect(screen.getByText('已选 2 台')).toBeTruthy();
  const zoom=screen.getByLabelText('缩放比例').textContent;
  fireEvent.pointerDown(canvas(),{pointerType:'touch',pointerId:10,clientX:100,clientY:100});
  fireEvent.pointerDown(canvas(),{pointerType:'touch',pointerId:11,clientX:200,clientY:100});
  fireEvent.pointerMove(canvas(),{pointerType:'touch',pointerId:11,clientX:300,clientY:100});
  expect(screen.getByLabelText('缩放比例').textContent).not.toBe(zoom);
  fireEvent.pointerUp(canvas(),{pointerId:10});fireEvent.pointerUp(canvas(),{pointerId:11});
  expect(localStorage.getItem(documentKey('test'))).toBeNull();
});
it('preserves native Space activation on buttons and cancels camera movement with Escape', () => {
  render(<Harness />);
  expect(fireEvent.keyDown(screen.getByRole('button',{name:'框选工具'}),{key:' '})).toBe(true);
  const before=screen.getByTestId('topology-stage').style.transform;
  fireEvent.pointerDown(canvas(),{pointerId:1,button:0,clientX:100,clientY:100});
  fireEvent.pointerMove(canvas(),{pointerId:1,clientX:200,clientY:180});
  fireEvent.keyDown(canvas(),{key:'Escape'});
  expect(screen.getByTestId('topology-stage').style.transform).toBe(before);
});
it('isolates layouts per service and reports failed local persistence', () => {
  render(<Harness scope="service-a" />);
  drag(screen.getByRole('button',{name:'查看设备：a'}));
  cleanup(); render(<Harness scope="service-b" />);
  expect(screen.getByRole('button',{name:'查看设备：a'}).style.left).toBe(`${layout.nodes[0].x}px`);
  vi.spyOn(Storage.prototype,'setItem').mockImplementation(() => { throw new Error('quota'); });
  drag(screen.getByRole('button',{name:'查看设备：a'}));
  expect(screen.getByRole('alert').textContent).toContain('本机存储不可用');
});
