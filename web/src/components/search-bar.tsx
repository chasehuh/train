"use client";

import { FormEvent } from "react";
import {
  formatYmdDisplay,
  hhmmssToInputTime,
  inputDateToYmd,
  inputTimeToHhmmss,
  ymdToInputDate,
} from "@/lib/trains";

export type SearchQuery = {
  dep: string;
  arr: string;
  date: string;
  time: string;
  passengers: number;
};

type SearchBarProps = {
  carrier: "srt" | "korail";
  query: SearchQuery;
  busy: boolean;
  onChange: (next: SearchQuery) => void;
  onSearch: (query: SearchQuery) => void;
};

export function SearchBar({
  carrier,
  query,
  busy,
  onChange,
  onSearch,
}: SearchBarProps) {
  const depPlaceholder = carrier === "srt" ? "수서" : "서울";
  const arrPlaceholder = carrier === "srt" ? "대전" : "동대구";

  function swap() {
    onChange({ ...query, dep: query.arr, arr: query.dep });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    onSearch(query);
  }

  const dateLabel = formatYmdDisplay(query.date);
  const timeLabel = hhmmssToInputTime(query.time);

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-2xl border border-[var(--line)] bg-[rgba(17,20,27,0.72)] p-3 shadow-[0_12px_40px_rgba(0,0,0,0.28)] backdrop-blur-md md:p-4"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_auto_1fr_1.2fr_0.7fr_auto] lg:items-end">
        <label className="block">
          <span className="label">출발역</span>
          <div className="relative mt-1">
            <input
              className="field pr-9 text-base font-medium"
              value={query.dep}
              onChange={(e) => onChange({ ...query, dep: e.target.value })}
              placeholder={depPlaceholder}
              required
              autoComplete="off"
            />
            <span
              aria-hidden
              className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-[var(--accent-2)]"
            >
              ✦
            </span>
          </div>
        </label>

        <div className="flex items-end justify-center sm:col-span-2 lg:col-span-1 lg:pb-0.5">
          <button
            type="button"
            onClick={swap}
            aria-label="Swap stations"
            className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--line)] bg-[var(--bg2)] text-sm text-[var(--accent)] transition hover:border-[rgba(232,165,75,0.45)]"
          >
            ⇄
          </button>
        </div>

        <label className="block sm:col-start-2 sm:row-start-1 lg:col-auto lg:row-auto">
          <span className="label">도착역</span>
          <div className="relative mt-1">
            <input
              className="field pr-9 text-base font-medium"
              value={query.arr}
              onChange={(e) => onChange({ ...query, arr: e.target.value })}
              placeholder={arrPlaceholder}
              required
              autoComplete="off"
            />
            <span
              aria-hidden
              className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-[var(--muted)]"
            >
              ⌖
            </span>
          </div>
        </label>

        <label className="block">
          <span className="label">출발일</span>
          <div className="mt-1 grid grid-cols-[1fr_auto] gap-2">
            <input
              className="field font-mono text-sm"
              type="date"
              value={ymdToInputDate(query.date)}
              onChange={(e) =>
                onChange({
                  ...query,
                  date: inputDateToYmd(e.target.value) || query.date,
                })
              }
              required
            />
            <input
              className="field w-[6.5rem] font-mono text-sm"
              type="time"
              value={timeLabel}
              onChange={(e) =>
                onChange({
                  ...query,
                  time: inputTimeToHhmmss(e.target.value),
                })
              }
              required
            />
          </div>
          <p className="mt-1 font-mono text-[10px] text-[var(--muted)]">
            {dateLabel} {timeLabel}
          </p>
        </label>

        <label className="block">
          <span className="label">인원</span>
          <div className="relative mt-1">
            <select
              className="field appearance-none pr-8 text-base font-medium"
              value={query.passengers}
              onChange={(e) =>
                onChange({ ...query, passengers: Number(e.target.value) })
              }
            >
              {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                <option key={n} value={n}>
                  총 {n}명
                </option>
              ))}
            </select>
            <span
              aria-hidden
              className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-[var(--muted)]"
            >
              ☺
            </span>
          </div>
        </label>

        <button
          type="submit"
          disabled={busy}
          className="h-[2.65rem] w-full rounded-full bg-[linear-gradient(145deg,var(--accent),#c8842f)] px-5 text-sm font-semibold text-[#1a1208] transition enabled:hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 lg:min-w-[9.5rem]"
        >
          {busy ? "조회 중…" : "열차 조회하기"}
        </button>
      </div>
    </form>
  );
}
