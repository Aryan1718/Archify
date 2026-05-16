export class ArchifyError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "ArchifyError";
    this.code = options.code ?? "ARCHIFY_ERROR";
    this.exitCode = options.exitCode ?? 1;
  }
}
