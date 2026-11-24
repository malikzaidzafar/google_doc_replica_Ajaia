"use client";

import { useEditorState, type Editor } from "@tiptap/react";
import { IconButton } from "../ui/Button";
import { Select } from "../ui/Field";
import type { IconName } from "../ui/icons";

const BLOCK_STYLES = [
  { value: "p", label: "Normal text" },
  { value: "1", label: "Heading 1" },
  { value: "2", label: "Heading 2" },
  { value: "3", label: "Heading 3" },
] as const;

const Divider = () => <span className="mx-1 h-5 w-px bg-zinc-200" aria-hidden="true" />;

export default function Toolbar({ editor, disabled }: { editor: Editor; disabled: boolean }) {
  // Re-render only when the formatting at the cursor changes.
  const s = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      bold: e.isActive("bold"),
      italic: e.isActive("italic"),
      underline: e.isActive("underline"),
      bullet: e.isActive("bulletList"),
      ordered: e.isActive("orderedList"),
      block: ([1, 2, 3] as const).find((level) => e.isActive("heading", { level }))?.toString() ?? "p",
      canUndo: e.can().undo(),
      canRedo: e.can().redo(),
    }),
  });
  const chain = () => editor.chain().focus();

  const setBlock = (value: string) =>
    value === "p"
      ? chain().setParagraph().run()
      : chain().toggleHeading({ level: Number(value) as 1 | 2 | 3 }).run();

  const tool = (icon: IconName, label: string, pressed: boolean | undefined, run: () => void, off = false) => (
    <IconButton
      icon={icon}
      label={label}
      pressed={pressed}
      disabled={disabled || off}
      onMouseDown={(e) => e.preventDefault()} // keep the editor's selection
      onClick={run}
    />
  );

  return (
    <div
      role="toolbar"
      aria-label="Formatting"
      className="mx-auto flex w-fit max-w-full flex-wrap items-center gap-0.5 rounded-xl border border-zinc-200/80 bg-white/95 px-1.5 py-1 shadow-card backdrop-blur"
    >
      {tool("undo", "Undo (Ctrl+Z)", undefined, () => chain().undo().run(), !s.canUndo)}
      {tool("redo", "Redo (Ctrl+Shift+Z)", undefined, () => chain().redo().run(), !s.canRedo)}
      <Divider />
      <Select
        aria-label="Text style"
        compact
        value={s.block}
        disabled={disabled}
        onChange={(e) => setBlock(e.target.value)}
        className="w-36 border-transparent shadow-none hover:bg-zinc-100"
      >
        {BLOCK_STYLES.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </Select>
      <Divider />
      {tool("bold", "Bold (Ctrl+B)", s.bold, () => chain().toggleBold().run())}
      {tool("italic", "Italic (Ctrl+I)", s.italic, () => chain().toggleItalic().run())}
      {tool("underline", "Underline (Ctrl+U)", s.underline, () => chain().toggleUnderline().run())}
      <Divider />
      {tool("list", "Bulleted list", s.bullet, () => chain().toggleBulletList().run())}
      {tool("listOrdered", "Numbered list", s.ordered, () => chain().toggleOrderedList().run())}
    </div>
  );
}
