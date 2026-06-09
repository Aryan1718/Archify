export const DOC_TYPES = {
  archify: {
    id: "archify",
    outputFile: "archify.md"
  },
  tech_stack: {
    id: "tech_stack",
    outputFile: "TECH_STACK.md"
  },
  api_design: {
    id: "api_design",
    outputFile: "API_DESIGN.md"
  },
  data_model: {
    id: "data_model",
    outputFile: "DATA_MODEL.md"
  },
  conventions: {
    id: "conventions",
    outputFile: "CONVENTIONS.md"
  },
  glossary: {
    id: "glossary",
    outputFile: "GLOSSARY.md"
  },
  flows: {
    id: "flows",
    outputFile: "FLOWS.md"
  },
  test_cases: {
    id: "test_cases",
    outputFile: "TEST_CASES.md"
  }
};

export const DEFAULT_DOC_TYPE = "archify";
export const SUPPORTED_DOC_TYPES = Object.keys(DOC_TYPES);

export function getDocTypeSpec(docType = DEFAULT_DOC_TYPE) {
  return DOC_TYPES[docType] ?? null;
}

