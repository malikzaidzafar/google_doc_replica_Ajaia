// Client-side pre-check so users get instant feedback; the server validates again.

export const UPLOAD_ACCEPT = ".txt,.md,.docx";
const UPLOAD_TYPES = [".txt", ".md", ".docx"];
const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;

export function uploadProblem(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!UPLOAD_TYPES.includes(ext)) return "That file type isn't supported. Choose a .txt, .md or .docx file.";
  if (file.size === 0) return "That file is empty. Choose a file with some text in it.";
  if (file.size > MAX_UPLOAD_BYTES) return "That file is larger than 2 MB. Try a smaller file.";
  return null;
}
