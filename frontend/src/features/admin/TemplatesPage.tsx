import { Stack, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { TemplatesPanel } from '../templates/TemplatesPanel';

/** Catálogo global de plantillas de documento (solo admins, ADR-011). */
export function TemplatesPage() {
  const { t } = useTranslation();
  return (
    <Stack maw={1100}>
      <Title order={2}>{t('templates.title')}</Title>
      <TemplatesPanel scope={{ kind: 'global' }} canEdit />
    </Stack>
  );
}
