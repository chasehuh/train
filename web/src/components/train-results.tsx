"use client";

import {
  formatPrice,
  type SeatClass,
  type TrainResult,
  type TrainSelection,
} from "@/lib/trains";

type TrainResultsProps = {
  trains: TrainResult[];
  source: "live" | "mock" | null;
  searched: boolean;
  selection: TrainSelection | null;
  onSelect: (selection: TrainSelection) => void;
};

function SeatBox({
  train,
  seat,
  selected,
  onSelect,
}: {
  train: TrainResult;
  seat: SeatClass;
  selected: boolean;
  onSelect: () => void;
}) {
  const offer = seat === "general" ? train.general : train.special;
  const price = formatPrice(offer.price);
  const disabled = !offer.available;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onSelect}
      className={`min-w-[6.5rem] flex-1 rounded-xl border px-3 py-2.5 text-left transition sm:flex-none ${
        selected
          ? "border-[rgba(232,165,75,0.65)] bg-[rgba(232,165,75,0.14)] shadow-[inset_0_0_0_1px_rgba(232,165,75,0.25)]"
          : disabled
            ? "cursor-not-allowed border-[var(--line)] bg-[rgba(17,20,27,0.35)] opacity-45"
            : "border-[var(--line)] bg-[rgba(24,29,39,0.85)] hover:border-[rgba(232,165,75,0.35)]"
      }`}
    >
      <p className="text-[11px] font-medium tracking-wide text-[var(--muted)]">
        {offer.label}
      </p>
      <p
        className={`mt-0.5 text-sm font-semibold ${
          disabled ? "text-[var(--muted)]" : "text-[var(--text)]"
        }`}
      >
        {disabled ? "매진" : price || "선택"}
      </p>
      {!disabled && offer.state ? (
        <p className="mt-0.5 font-mono text-[10px] text-[var(--ok)]">
          {offer.state.includes("가능") ? "예약가능" : offer.state}
        </p>
      ) : null}
    </button>
  );
}

export function TrainResults({
  trains,
  source,
  searched,
  selection,
  onSelect,
}: TrainResultsProps) {
  if (!searched) {
    return (
      <div className="rise flex min-h-[28vh] flex-col items-center justify-center px-2 text-center">
        <p className="font-mono text-[11px] tracking-[0.18em] text-[var(--accent)] uppercase">
          Browse
        </p>
        <h2 className="mt-3 text-xl font-semibold tracking-tight text-[var(--text)]">
          Search trains first
        </h2>
        <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--muted)]">
          Pick stations and a departure window, then choose a seat class. Confirm
          starts a watch job for that exact train.
        </p>
      </div>
    );
  }

  if (trains.length === 0) {
    return (
      <div className="rise rounded-2xl border border-[var(--line)] bg-[rgba(17,20,27,0.45)] px-4 py-10 text-center">
        <p className="text-sm font-medium text-[var(--text)]">No trains found</p>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Try an earlier time or nearby stations.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {source === "mock" ? (
        <p className="rounded-full border border-[rgba(212,168,67,0.35)] bg-[rgba(212,168,67,0.08)] px-3 py-1.5 text-center font-mono text-[10px] text-[var(--warn)]">
          Mock timetable · live search needs Railway deploy of /v1/trains/search
        </p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {trains.map((train) => {
          const key = `${train.train_number}-${train.dep_time}`;
          const selectedGeneral =
            selection?.train.train_number === train.train_number &&
            selection.train.dep_time === train.dep_time &&
            selection.seat === "general";
          const selectedSpecial =
            selection?.train.train_number === train.train_number &&
            selection.train.dep_time === train.dep_time &&
            selection.seat === "special";

          return (
            <li
              key={key}
              className="message-in overflow-hidden rounded-2xl border border-[var(--line)] bg-[rgba(17,20,27,0.62)]"
            >
              <div className="flex">
                <div
                  className="w-1 shrink-0 bg-[var(--accent-2)]"
                  aria-hidden
                />
                <div className="flex min-w-0 flex-1 flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <span className="text-sm font-semibold text-[var(--accent-2)]">
                        {train.train_type}
                      </span>
                      <span className="font-mono text-[12px] text-[var(--muted)]">
                        {train.train_number}
                      </span>
                    </div>
                    <p className="mt-1 text-[15px] font-semibold tracking-tight text-[var(--text)]">
                      {train.dep} → {train.arr}
                      <span className="font-mono text-[13px] font-medium text-[var(--text)]">
                        ({train.dep_display} ~ {train.arr_display})
                      </span>
                    </p>
                    {train.duration_label ? (
                      <p className="mt-1 text-[12px] text-[var(--muted)]">
                        소요시간: {train.duration_label}
                      </p>
                    ) : null}
                  </div>

                  <div className="flex gap-2">
                    <SeatBox
                      train={train}
                      seat="general"
                      selected={selectedGeneral}
                      onSelect={() => onSelect({ train, seat: "general" })}
                    />
                    <SeatBox
                      train={train}
                      seat="special"
                      selected={selectedSpecial}
                      onSelect={() => onSelect({ train, seat: "special" })}
                    />
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
