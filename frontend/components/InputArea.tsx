"use client";

import type { KeyboardEvent } from "react";

type Props = {
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function InputArea({ value, disabled, onChange, onSubmit }: Props) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.nativeEvent.isComposing) {
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!disabled && value.trim()) {
        onSubmit();
      }
    }
  }

  return (
    <form
      className="flex gap-2 border-t border-white/10 bg-[#160b1f]/95 p-4 shadow-[0_-18px_40px_rgba(0,0,0,0.28)]"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label className="sr-only" htmlFor="chat-query">
        質問
      </label>
      <textarea
        id="chat-query"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        className="min-h-12 flex-1 resize-none rounded border border-white/15 bg-white/95 px-3 py-2 text-[#1a1020] outline-none transition placeholder:text-[#6e6075] focus:border-[#1de9ff] focus:shadow-[0_0_0_3px_rgba(29,233,255,0.24)] disabled:opacity-60"
        rows={2}
        maxLength={500}
        placeholder="スポーツに関する質問を入力"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="h-12 w-20 rounded bg-[#ff2d92] px-4 text-sm font-semibold text-white shadow-[0_0_20px_rgba(255,45,146,0.36)] transition hover:bg-[#ff4fa3] disabled:cursor-not-allowed disabled:bg-white/20 disabled:text-white/50 disabled:shadow-none"
      >
        送信
      </button>
    </form>
  );
}
