export type SeatClass = "general" | "special";

export type SeatOffer = {
  available: boolean;
  label: string;
  state?: string;
  price: number | null;
};

export type TrainResult = {
  carrier: "srt" | "korail";
  train_type: string;
  train_number: string;
  dep: string;
  arr: string;
  dep_date: string;
  dep_time: string;
  arr_time: string;
  dep_display: string;
  arr_display: string;
  duration_min: number | null;
  duration_label: string | null;
  general: SeatOffer;
  special: SeatOffer;
  has_seat: boolean;
};

export type TrainSearchResponse = {
  ok: boolean;
  carrier?: "srt" | "korail";
  dep?: string;
  arr?: string;
  date?: string;
  time?: string;
  trains?: TrainResult[];
  source?: "live" | "mock";
  error?: string;
  message?: string;
};

export type TrainSelection = {
  train: TrainResult;
  seat: SeatClass;
};

/** Fixture trains for local smoke when Railway search is undeployed. */
export function mockTrainResults(input: {
  carrier: "srt" | "korail";
  dep: string;
  arr: string;
  date: string;
}): TrainResult[] {
  const isSrt = input.carrier === "srt";
  const base: Omit<TrainResult, "train_type" | "train_number" | "dep_time" | "arr_time" | "dep_display" | "arr_display" | "duration_min" | "duration_label"> = {
    carrier: input.carrier,
    dep: input.dep,
    arr: input.arr,
    dep_date: input.date,
    general: {
      available: true,
      label: "일반실",
      state: "예약가능",
      price: isSrt ? 44800 : 43500,
    },
    special: {
      available: true,
      label: "특실",
      state: "예약가능",
      price: isSrt ? 62700 : 60900,
    },
    has_seat: true,
  };

  return [
    {
      ...base,
      train_type: isSrt ? "SRT" : "KTX",
      train_number: isSrt ? "345" : "201",
      dep_time: "050300",
      arr_time: "064600",
      dep_display: "05:03",
      arr_display: "06:46",
      duration_min: 103,
      duration_label: "1시간 43분",
    },
    {
      ...base,
      train_type: isSrt ? "SRT" : "KTX 산천",
      train_number: isSrt ? "347" : "101",
      dep_time: "063000",
      arr_time: "081200",
      dep_display: "06:30",
      arr_display: "08:12",
      duration_min: 102,
      duration_label: "1시간 42분",
      special: {
        available: false,
        label: "특실",
        state: "매진",
        price: isSrt ? 62700 : 60900,
      },
    },
    {
      ...base,
      train_type: isSrt ? "SRT" : "KTX",
      train_number: isSrt ? "351" : "113",
      dep_time: "080000",
      arr_time: "094500",
      dep_display: "08:00",
      arr_display: "09:45",
      duration_min: 105,
      duration_label: "1시간 45분",
      general: {
        available: false,
        label: "일반실",
        state: "매진",
        price: isSrt ? 44800 : 43500,
      },
      has_seat: true,
    },
  ];
}

export function formatYmdDisplay(ymd: string): string {
  if (!/^\d{8}$/.test(ymd)) return ymd;
  const y = ymd.slice(0, 4);
  const m = ymd.slice(4, 6);
  const d = ymd.slice(6, 8);
  const date = new Date(`${y}-${m}-${d}T12:00:00+09:00`);
  const weekday = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    weekday: "short",
  }).format(date);
  return `${y}-${m}-${d}(${weekday})`;
}

export function ymdToInputDate(ymd: string): string {
  if (!/^\d{8}$/.test(ymd)) return "";
  return `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}`;
}

export function inputDateToYmd(value: string): string {
  return value.replaceAll("-", "");
}

export function hhmmssToInputTime(hhmmss: string): string {
  if (!/^\d{6}$/.test(hhmmss)) return "00:00";
  return `${hhmmss.slice(0, 2)}:${hhmmss.slice(2, 4)}`;
}

export function inputTimeToHhmmss(value: string): string {
  const [h = "00", m = "00"] = value.split(":");
  return `${h.padStart(2, "0")}${m.padStart(2, "0")}00`;
}

export function formatPrice(price: number | null): string | null {
  if (price == null) return null;
  return `${price.toLocaleString("ko-KR")}원`;
}
