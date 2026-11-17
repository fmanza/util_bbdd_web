import { Badge, Box, Fieldset, Group, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { autoGrid } from './grid';

/**
 * Tarjeta del formulario de lanzamiento: un `fieldset` (rol `group` con el título como nombre accesible). Con errores
 * muestra una insignia; es decorativa (`aria-hidden`) porque cada campo anuncia su propio error.
 */
export function LaunchCard({
  title,
  errors,
  span,
  cols,
  children,
}: {
  title: string;
  errors: number;
  span?: 1 | 'full' | undefined;
  cols: number;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <Fieldset
      legend={
        <Group gap="xs" wrap="nowrap">
          <Text component="span" fw={600} size="sm">
            {title}
          </Text>
          {errors > 0 && (
            <Badge color="red" size="xs" aria-hidden>
              {t('runs.launch.cardErrors', { count: errors })}
            </Badge>
          )}
        </Group>
      }
      style={{
        gridColumn: span === 'full' ? '1 / -1' : undefined,
        borderColor: errors > 0 ? 'var(--mantine-color-error)' : undefined,
        minWidth: 0,
      }}
    >
      <Box style={autoGrid(13, cols)}>{children}</Box>
    </Fieldset>
  );
}
