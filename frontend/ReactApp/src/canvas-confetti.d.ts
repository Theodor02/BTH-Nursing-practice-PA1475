declare module 'canvas-confetti' {
  interface ConfettiOptions {
    particleCount?: number;
    angle?: number;
    spread?: number;
    origin?: { x: number; y: number };
    colors?: string[];
    startVelocity?: number;
    decay?: number;
    gravity?: number;
    drift?: number;
    ticks?: number;
    shapes?: string[];
    scalar?: number;
    zIndex?: number;
    disableForReducedMotion?: boolean;
  }

  interface Confetti {
    (options?: ConfettiOptions): Promise<void>;
    reset(): void;
    shapeFromText(options: any): any;
    shapeFromPath(options: any): any;
  }

  const confetti: Confetti;
  export default confetti;
}
