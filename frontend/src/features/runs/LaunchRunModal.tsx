import { Box, Flex, Loader, Modal } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import type { ProjectConnection } from '../projects/useProjects';
import { categorize } from './launch/launchLayout';
import { LaunchForm } from './launch/LaunchForm';
import { OperationRail } from './launch/OperationRail';
import { useOperations } from './useRuns';

/**
 * «Lanzar ejecución»: modal ancho (pantalla completa en móvil) con la lista de operaciones a la izquierda y el
 * formulario de la elegida a la derecha. Al abrir se elige la primera de la lista (Documentación si está).
 */
export function LaunchRunModal({
  projectId,
  connections,
  opened,
  onClose,
}: {
  projectId: number;
  connections: ProjectConnection[];
  opened: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const operations = useOperations();
  const mobile = useMediaQuery('(max-width: 48em)');
  const [name, setName] = useState<string | null>(null);
  // `form=false` (p. ej. `migrate_apply`) se lanza desde otra pantalla.
  const launchable = (operations.data ?? []).filter((op) => op.form !== false);
  const first = categorize(launchable)[0]?.operations[0];
  const selected = launchable.find((op) => op.name === (name ?? first?.name));

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('runs.launch.title')}
      // `calc(...)` pasa tal cual por el conversor de unidades de Mantine.
      size="calc(min(1400px, 96vw))"
      fullScreen={mobile === true}
      styles={{ title: { fontWeight: 700, fontSize: 'var(--mantine-font-size-lg)' } }}
    >
      {operations.isError && <ErrorAlert error={operations.error} />}
      {operations.isPending && <Loader aria-label={t('common.loading')} />}
      {selected && (
        <Flex direction={{ base: 'column', md: 'row' }} gap="lg" align="flex-start">
          <Box w={{ base: '100%', md: 260 }} style={{ flexShrink: 0 }}>
            <OperationRail operations={launchable} value={selected.name} onChange={setName} />
          </Box>
          <Box style={{ flex: 1, minWidth: 0 }} w="100%">
            <LaunchForm
              key={selected.name}
              projectId={projectId}
              operation={selected}
              connections={connections}
              onClose={onClose}
            />
          </Box>
        </Flex>
      )}
    </Modal>
  );
}
