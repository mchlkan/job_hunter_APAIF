import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, getCandidate, getJobs, getProfile, getStats, uploadCv, type JobFilters } from "@/lib/api";

export function useJobs(filters: JobFilters = {}) {
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: () => getJobs(filters),
  });
}

export function useStats() {
  return useQuery({ queryKey: ["stats"], queryFn: getStats });
}

export function useCandidate() {
  return useQuery({
    queryKey: ["candidate"],
    queryFn: getCandidate,
    retry: (failureCount, error) => error instanceof ApiError && error.status === 404 ? false : failureCount < 2,
  });
}

export function useProfile() {
  return useQuery({ queryKey: ["profile"], queryFn: getProfile });
}

export function useUploadCv() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadCv,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidate"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
