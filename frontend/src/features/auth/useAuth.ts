import { useMantineColorScheme } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, CSRF_HEADER, ensureOk, isApiError, unwrap } from '../../api/client';
import { setLanguage } from '../../i18n';
import type { components } from '../../api/schema';

export type Me = components['schemas']['Me'];
export type LoginRequest = components['schemas']['LoginRequest'];
export type PasswordChange = components['schemas']['PasswordChange'];
export type ColorScheme = Me['color_scheme'];
export type Language = Me['language'];
export type Permission = Me['permissions'][number];
export type RoleRef = Me['role'];

/** El rol de `me` tiene `permission` (ADR-014). */
export function can(me: Me | null | undefined, permission: Permission): boolean {
  return me?.permissions.includes(permission) ?? false;
}

export const meQueryKey = ['auth', 'me'] as const;

// La política real la valida el servidor (UBW_PASSWORD_MIN_LENGTH); aquí solo se adelanta el mínimo por defecto.
export const PASSWORD_MIN_LENGTH = 12;

/** Usuario de la sesión actual; `null` si no hay sesión (401). */
export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<Me | null> => {
      try {
        return unwrap(await api.GET('/api/v1/auth/me'));
      } catch (error) {
        if (isApiError(error, 401)) {
          return null;
        }
        throw error;
      }
    },
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: LoginRequest): Promise<Me> => {
      // Token CSRF previo al login: también pone la cookie `ubw_csrf`.
      const { csrf_token } = unwrap(await api.GET('/api/v1/auth/csrf'));
      return unwrap(await api.POST('/api/v1/auth/login', { body, headers: { [CSRF_HEADER]: csrf_token } }));
    },
    onSuccess: (me) => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== meQueryKey[0] });
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => ensureOk(await api.POST('/api/v1/auth/logout')),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (body: PasswordChange) => ensureOk(await api.POST('/api/v1/auth/password', { body })),
  });
}

/**
 * Guarda el tema en la cuenta con actualización optimista: el tema y la caché de `me` cambian al instante, y si el
 * servidor falla vuelven los dos al valor anterior. Mientras se guarda, el menú desactiva las opciones (sin carreras
 * entre dos clics seguidos).
 */
export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  return useMutation({
    mutationFn: async (color_scheme: ColorScheme): Promise<Me> =>
      unwrap(await api.PATCH('/api/v1/auth/me/preferences', { body: { color_scheme } })),
    onMutate: async (next) => {
      await queryClient.cancelQueries({ queryKey: meQueryKey });
      const previousMe = queryClient.getQueryData<Me | null>(meQueryKey);
      const previousScheme = colorScheme;
      setColorScheme(next);
      if (previousMe) queryClient.setQueryData<Me>(meQueryKey, { ...previousMe, color_scheme: next });
      return { previousMe, previousScheme };
    },
    onError: (_error, _next, context) => {
      if (!context) return;
      setColorScheme(context.previousScheme);
      if (context.previousMe !== undefined) queryClient.setQueryData(meQueryKey, context.previousMe);
    },
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

/**
 * Guarda el idioma en la cuenta con actualización optimista, como el tema: la interfaz y la caché de `me` cambian al
 * instante, y si el servidor falla vuelven los dos al idioma anterior.
 */
export function useUpdateLanguage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (language: Language): Promise<Me> =>
      unwrap(await api.PATCH('/api/v1/auth/me/preferences', { body: { language } })),
    onMutate: async (next) => {
      await queryClient.cancelQueries({ queryKey: meQueryKey });
      const previousMe = queryClient.getQueryData<Me | null>(meQueryKey);
      await setLanguage(next);
      if (previousMe) queryClient.setQueryData<Me>(meQueryKey, { ...previousMe, language: next });
      return { previousMe };
    },
    onError: async (_error, _next, context) => {
      if (!context?.previousMe) return;
      await setLanguage(context.previousMe.language);
      queryClient.setQueryData(meQueryKey, context.previousMe);
    },
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

/** Ruta interna segura a la que volver tras el login (evita redirecciones abiertas). */
export function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : '/';
}
