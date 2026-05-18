/// <reference types="vite/client" />

declare module '@deck.gl/react' {
  const DeckGL: any;
  export default DeckGL;
}

declare module '@deck.gl/layers' {
  export class ScatterplotLayer<T = unknown> {
    constructor(props: Record<string, unknown>);
  }
}
