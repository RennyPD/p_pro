export const weekDays = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export type ScheduleBlock = {
  day_of_week: string;
  start_time: string;
  end_time: string;
  room: string;
  modality: string;
  virtual_url?: string;
};

export type ScheduleTimes = Omit<ScheduleBlock, "day_of_week"> & {
  days_of_week: string[] | string;
  blocks?: ScheduleBlock[];
};

export function scheduleBlocks(item: ScheduleTimes): ScheduleBlock[] {
  if (item.blocks) return item.blocks;
  const days = Array.isArray(item.days_of_week) ? item.days_of_week : item.days_of_week.split(",");
  return days.map(day => ({
    day_of_week: day.trim(),
    start_time: item.start_time,
    end_time: item.end_time,
    room: item.room,
    modality: item.modality,
  }));
}
