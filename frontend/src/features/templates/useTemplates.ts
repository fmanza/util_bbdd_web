import { type QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type DocumentTemplate = components['schemas']['TemplateOut'];
export type TemplateKind = DocumentTemplate['kind'];

/** Catálogo global (lo gestionan los admins) o plantillas de un proyecto (más las globales, en solo lectura). */
export type TemplateScope = { kind: 'global' } | { kind: 'project'; projectId: number };

export interface TemplateUpload {
  file: File;
  name: string;
}

export interface TemplateChange {
  id: string;
  name?: string;
  /** `null`: vuelve al estilo por defecto (Word: el de util_bbdd; Excel: `TableStyleMedium2`). */
  table_style?: string | null;
}

const templatesKey = (scope: TemplateScope) =>
  scope.kind === 'global'
    ? (['document-templates'] as const)
    : (['projects', scope.projectId, 'document-templates'] as const);

/** Una plantilla global aparece en todos los proyectos: se refrescan todas las listas. */
function invalidate(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (query) => query.queryKey.includes('document-templates'),
  });
}

export function useTemplates(scope: TemplateScope, enabled = true) {
  return useQuery({
    queryKey: templatesKey(scope),
    enabled,
    queryFn: async () =>
      scope.kind === 'global'
        ? unwrap(await api.GET('/api/v1/document-templates'))
        : unwrap(
            await api.GET('/api/v1/projects/{project_id}/document-templates', {
              params: { path: { project_id: scope.projectId } },
            }),
          ),
  });
}

function formData(body: { file: string; name?: string | null }) {
  const form = new FormData();
  form.append('file', body.file as unknown as Blob);
  if (body.name) form.append('name', body.name);
  return form;
}

/** Sube una plantilla (`multipart/form-data`; el cliente añade la cabecera CSRF). */
export function useUploadTemplate(scope: TemplateScope) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, name }: TemplateUpload) => {
      const body = { file: file as unknown as string, name: name.trim() || null };
      return scope.kind === 'global'
        ? unwrap(await api.POST('/api/v1/admin/document-templates', { body, bodySerializer: formData }))
        : unwrap(
            await api.POST('/api/v1/projects/{project_id}/document-templates', {
              params: { path: { project_id: scope.projectId } },
              body,
              bodySerializer: formData,
            }),
          );
    },
    onSuccess: () => invalidate(queryClient),
  });
}

export function useUpdateTemplate(scope: TemplateScope) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: TemplateChange) =>
      scope.kind === 'global'
        ? unwrap(
            await api.PATCH('/api/v1/admin/document-templates/{template_id}', {
              params: { path: { template_id: id } },
              body,
            }),
          )
        : unwrap(
            await api.PATCH('/api/v1/projects/{project_id}/document-templates/{template_id}', {
              params: { path: { project_id: scope.projectId, template_id: id } },
              body,
            }),
          ),
    onSuccess: () => invalidate(queryClient),
  });
}

export function useDeleteTemplate(scope: TemplateScope) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      ensureOk(
        scope.kind === 'global'
          ? await api.DELETE('/api/v1/admin/document-templates/{template_id}', {
              params: { path: { template_id: id } },
            })
          : await api.DELETE('/api/v1/projects/{project_id}/document-templates/{template_id}', {
              params: { path: { project_id: scope.projectId, template_id: id } },
            }),
      ),
    onSuccess: () => invalidate(queryClient),
  });
}

/** Descarga: las globales también se sirven desde el proyecto (cualquier miembro). */
export function templateFileUrl(scope: TemplateScope, id: string): string {
  const template = encodeURIComponent(id);
  return scope.kind === 'global'
    ? `/api/v1/document-templates/${template}/file`
    : `/api/v1/projects/${scope.projectId}/document-templates/${template}/file`;
}

export const baseTemplateUrl = (kind: TemplateKind) => `/api/v1/document-templates/base/${kind}`;
