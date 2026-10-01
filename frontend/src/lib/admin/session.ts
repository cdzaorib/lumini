export type RequestTicket = {
  credential: string;
  signal: AbortSignal;
  isCurrent: () => boolean;
};

// Tokens live only in this in-memory instance. Every logout/login/unmount
// invalidates old work, even when a fetch implementation ignores abort.
export class AdminSession {
  private credential: string | null = null;
  private generation = 0;
  private controller = new AbortController();

  start(credential: string): RequestTicket {
    this.clear();
    this.credential = credential;
    return this.capture()!;
  }

  clear(): void {
    this.controller.abort();
    this.controller = new AbortController();
    this.credential = null;
    this.generation += 1;
  }

  capture(): RequestTicket | null {
    if (!this.credential) return null;
    const generation = this.generation;
    return {
      credential: this.credential,
      signal: this.controller.signal,
      isCurrent: () => generation === this.generation && this.credential !== null,
    };
  }
}
