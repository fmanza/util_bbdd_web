import { Alert, type AlertProps, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';

interface ErrorAlertProps extends Omit<AlertProps, 'title' | 'children'> {
  error: unknown;
}

/** Muestra el *problem details* de un `ApiError` (título, detalle y referencia para soporte), nunca trazas. */
export function ErrorAlert({ error, ...props }: ErrorAlertProps) {
  const { t } = useTranslation();
  // La API responde en el idioma de `Accept-Language` (ADR-015). Una respuesta que no es suya (proxy, caída) no trae
  // `code`: su título sale de las traducciones por estado HTTP.
  const title =
    error instanceof ApiError
      ? error.problem.code
        ? error.problem.title
        : t(`errors.http.${error.problem.status}`, { defaultValue: t('common.error') })
      : t('common.error');
  const detail = error instanceof ApiError ? error.problem.detail : t('common.errorBody');
  const reference = error instanceof ApiError ? error.problem.request_id : undefined;
  return (
    <Alert color="red" role="alert" title={title} {...props}>
      {detail}
      {reference && (
        <Text size="xs" c="dimmed" mt={4}>
          {t('common.reference', { id: reference })}
        </Text>
      )}
    </Alert>
  );
}
