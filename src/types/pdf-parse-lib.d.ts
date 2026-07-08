// pdf-parse's internal module (imported directly to skip its debug
// self-test on plain `import "pdf-parse"`) ships no type declarations of
// its own, so we declare the minimal shape we actually use.
declare module "pdf-parse/lib/pdf-parse.js" {
  interface PdfParseResult {
    text: string;
    numpages: number;
    numrender: number;
    info: Record<string, unknown>;
    metadata: unknown;
    version: string;
  }

  type PdfParse = (
    dataBuffer: Buffer | Uint8Array,
    options?: Record<string, unknown>,
  ) => Promise<PdfParseResult>;

  const pdfParse: PdfParse;
  export default pdfParse;
}
