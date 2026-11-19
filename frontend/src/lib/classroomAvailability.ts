import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import { api } from "./api";
import type { ApiSchema } from "./apiTypes";

export type ClassroomAvailability = ApiSchema<"ClassroomAvailability">;

export type AvailabilityQuery = {
  days: string[];
  start: string;
  end: string;
  capacity: number;
  period: string;
  sectionId?: number | null;
  enabled?: boolean;
};

/** Classrooms with their status (available / busy / small / retired) for a time slot. */
export function useClassroomAvailability({
  days,
  start,
  end,
  capacity,
  period,
  sectionId,
  enabled = true,
}: AvailabilityQuery) {
  const userId = useAuthStore(state => state.user?.user_id);
  const ready = days.length > 0 && Boolean(start) && Boolean(end) && start < end;
  const params = {
    days: days.join(","),
    start_time: start.slice(0, 5),
    end_time: end.slice(0, 5),
    capacity: capacity || 1,
    period_name: period,
    section_id: sectionId || undefined,
  };
  const query = useQuery({
    queryKey: ["classroom-availability", userId, params],
    queryFn: () =>
      api
        .get<ClassroomAvailability[]>("/scheduling/classrooms/availability", { params })
        .then(response => response.data),
    enabled: ready && enabled,
  });
  return { ...query, ready, rooms: query.data ?? [] };
}

export const freeRoomsLabel = (rooms: ClassroomAvailability[]) => {
  const free = rooms.filter(room => room.status === "available").length;
  return free === 1 ? "1 aula libre en ese horario" : `${free} aulas libres en ese horario`;
};
