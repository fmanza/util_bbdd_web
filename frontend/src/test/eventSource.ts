import { act } from '@testing-library/react';
import { vi } from 'vitest';

type Listener = (event: MessageEvent<string>) => void;

/** `EventSource` simulado: los tests emiten eventos SSE con `emit()` y fallos con `fail()`. */
export class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  closed = false;
  onerror: ((event: Event) => void) | null = null;
  private listeners = new Map<string, Listener[]>();

  constructor(url: string | URL) {
    this.url = String(url);
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data: unknown) {
    act(() => {
      for (const listener of this.listeners.get(type) ?? []) {
        listener(new MessageEvent(type, { data: JSON.stringify(data) }));
      }
    });
  }

  fail() {
    act(() => this.onerror?.(new Event('error')));
  }
}

export function stubEventSource() {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
  return FakeEventSource;
}
