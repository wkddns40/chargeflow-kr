/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEMO_MODE?: string;
  readonly VITE_ENABLE_LLM_SEARCH?: string;
  readonly VITE_ENABLE_VIEWPORT_STATIONS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '@deck.gl/react' {
  const DeckGL: any;
  export default DeckGL;
}

declare module '@deck.gl/layers' {
  export class ScatterplotLayer<T = unknown> {
    constructor(props: Record<string, unknown>);
  }
}
