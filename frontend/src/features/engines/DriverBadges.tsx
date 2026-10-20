import { Badge, Group } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { Engine } from './useEngines';

/** Drivers del motor: en azul los instalados en el servidor; en gris, los que faltan. */
export function DriverBadges({ engine }: { engine: Engine }) {
  const { t } = useTranslation();
  return (
    <Group gap={4}>
      {engine.drivers.map((driver) => (
        <Badge
          key={driver.name}
          color={driver.installed ? 'blue' : 'gray'}
          variant={driver.installed ? 'light' : 'outline'}
          title={driver.installed ? t('engines.installed') : t('engines.notInstalled')}
        >
          {driver.name}
          {!driver.installed && ` · ${t('engines.notInstalledShort')}`}
        </Badge>
      ))}
    </Group>
  );
}
