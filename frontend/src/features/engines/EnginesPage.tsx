import { Anchor, Badge, Center, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { DriverBadges } from './DriverBadges';
import { useEngines } from './useEngines';

export function YesNo({ value }: { value: boolean }) {
  const { t } = useTranslation();
  return (
    <Badge color={value ? 'green' : 'gray'} variant="light">
      {value ? t('common.yes') : t('common.no')}
    </Badge>
  );
}

export function EnginesPage() {
  const { t } = useTranslation();
  const { data, isPending, isError, error } = useEngines();

  return (
    <Stack>
      <Title order={2}>{t('engines.title')}</Title>
      <Text c="dimmed">{t('engines.intro')}</Text>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <Table.ScrollContainer minWidth={900}>
          <Table striped highlightOnHover>
            <Table.Caption>{t('engines.matrixCaption')}</Table.Caption>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('engines.engine')}</Table.Th>
                <Table.Th>{t('engines.versions')}</Table.Th>
                <Table.Th>{t('engines.port')}</Table.Th>
                <Table.Th>{t('engines.drivers')}</Table.Th>
                <Table.Th>{t('engines.async')}</Table.Th>
                <Table.Th>{t('engines.migrateSource')}</Table.Th>
                <Table.Th>{t('engines.migrateTarget')}</Table.Th>
                <Table.Th>{t('engines.readiness')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((engine) => (
                <Table.Tr key={engine.db_type}>
                  <Table.Th scope="row">
                    <Anchor component={Link} to={`/engines/${engine.db_type}`}>
                      {engine.name}
                    </Anchor>
                  </Table.Th>
                  <Table.Td>{engine.version_range || '—'}</Table.Td>
                  <Table.Td>{engine.default_port ?? '—'}</Table.Td>
                  <Table.Td>
                    <DriverBadges engine={engine} />
                  </Table.Td>
                  <Table.Td>
                    <YesNo value={engine.capabilities.async_supported} />
                  </Table.Td>
                  <Table.Td>
                    <YesNo value={engine.capabilities.migrate_source} />
                  </Table.Td>
                  <Table.Td>
                    <YesNo value={engine.capabilities.migrate_target} />
                  </Table.Td>
                  <Table.Td>
                    <YesNo value={engine.capabilities.readiness} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  );
}
