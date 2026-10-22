import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Project = components['schemas']['ProjectOut'];
export type ProjectRole = Project['my_role'];
export type Member = components['schemas']['MemberOut'];
export type ProjectConnection = components['schemas']['ProjectConnectionOut'];

export const PAGE_SIZE = 50;
const RANK: Record<ProjectRole, number> = { viewer: 1, editor: 2, owner: 3 };

/** El rol `role` llega al menos a `minimum` (viewer < editor < owner). */
export function canRole(role: ProjectRole | undefined, minimum: ProjectRole): boolean {
  return role !== undefined && RANK[role] >= RANK[minimum];
}

export function useProjects(q: string, page: number) {
  return useQuery({
    queryKey: ['projects', { q, page }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects', {
          params: { query: { q: q || null, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useProject(id: number) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/projects/{project_id}', { params: { path: { project_id: id } } })),
    enabled: Number.isInteger(id) && id > 0,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['ProjectCreate']) =>
      unwrap(await api.POST('/api/v1/projects', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useUpdateProject(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['ProjectUpdate']) =>
      unwrap(
        await api.PATCH('/api/v1/projects/{project_id}', { params: { path: { project_id: id } }, body }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useDeleteProject(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      ensureOk(await api.DELETE('/api/v1/projects/{project_id}', { params: { path: { project_id: id } } })),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['projects', id] });
      return queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useMembers(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'members'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/members', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export function useAddMember(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['MemberCreate']) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/members', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'members'] }),
  });
}

export function useUpdateMember(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, role }: { userId: number; role: ProjectRole }) =>
      unwrap(
        await api.PATCH('/api/v1/projects/{project_id}/members/{user_id}', {
          params: { path: { project_id: projectId, user_id: userId } },
          body: { role },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', projectId] }),
  });
}

export function useRemoveMember(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: number) =>
      ensureOk(
        await api.DELETE('/api/v1/projects/{project_id}/members/{user_id}', {
          params: { path: { project_id: projectId, user_id: userId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useProjectConnections(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'connections'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/connections', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

export function useAddProjectConnection(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['ProjectConnectionCreate']) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/connections', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'connections'] }),
  });
}

export function useRemoveProjectConnection(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (alias: string) =>
      ensureOk(
        await api.DELETE('/api/v1/projects/{project_id}/connections/{alias}', {
          params: { path: { project_id: projectId, alias } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'connections'] }),
  });
}
