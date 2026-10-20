import {
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Code,
  Group,
  List,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { DriverBadges } from './DriverBadges';
import { useEngine } from './useEngines';

export function EngineDetailPage() {
  const { t } = useTranslation();
  const { dbType } = useParams();
  const { data: engine, isPending, isError, error } = useEngine(dbType);

  if (isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (isError) {
    return <ErrorAlert error={error} />;
  }

  return (
    <Stack maw={1000}>
      <Group justify="space-between">
        <Title order={2}>{engine.name}</Title>
        <Button component={Link} to={`/connections/new?db_type=${engine.db_type}`}>
          {t('engines.newConnection')}
        </Button>
      </Group>
      <Text>{engine.description}</Text>
      <Card withBorder>
        <Table>
          <Table.Tbody>
            <Table.Tr>
              <Table.Th>{t('engines.versions')}</Table.Th>
              <Table.Td>{engine.version_range || '—'}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Th>{t('engines.port')}</Table.Th>
              <Table.Td>{engine.default_port ?? '—'}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Th>{t('engines.drivers')}</Table.Th>
              <Table.Td>
                <DriverBadges engine={engine} />
              </Table.Td>
            </Table.Tr>
            {engine.install_command && (
              <Table.Tr>
                <Table.Th>{t('engines.install')}</Table.Th>
                <Table.Td>
                  <Code>{engine.install_command}</Code>
                </Table.Td>
              </Table.Tr>
            )}
            {engine.url_docs && (
              <Table.Tr>
                <Table.Th>{t('engines.docs')}</Table.Th>
                <Table.Td>
                  <Anchor href={engine.url_docs} target="_blank" rel="noopener noreferrer">
                    {engine.url_docs}
                  </Anchor>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Card>
      {engine.system_requirements.length > 0 && (
        <Stack gap="xs">
          <Title order={3}>{t('engines.requirements')}</Title>
          <List>
            {engine.system_requirements.map((requirement) => (
              <List.Item key={requirement}>{requirement}</List.Item>
            ))}
          </List>
        </Stack>
      )}
      <Stack gap="xs">
        <Title order={3}>{t('engines.features')}</Title>
        <Group gap={6}>
          {engine.features.map((feature) => (
            <Badge key={feature} variant="light" color="gray">
              {feature}
            </Badge>
          ))}
        </Group>
      </Stack>
      <Stack gap="xs">
        <Title order={3}>{t('engines.params')}</Title>
        <Table.ScrollContainer minWidth={800}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('engines.paramName')}</Table.Th>
                <Table.Th>{t('engines.paramType')}</Table.Th>
                <Table.Th>{t('engines.paramDefault')}</Table.Th>
                <Table.Th>{t('engines.paramDescription')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {engine.params.map((param) => (
                <Table.Tr key={param.name}>
                  <Table.Td>
                    <Group gap={4}>
                      <Code>{param.name}</Code>
                      {param.required && (
                        <Badge size="xs" color="red" variant="light">
                          {t('engines.required')}
                        </Badge>
                      )}
                      {param.kind !== 'plain' && (
                        <Badge size="xs" variant="outline">
                          {t(`engines.kinds.${param.kind}`)}
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {param.type}
                    {param.options && ` (${param.options.filter(Boolean).join(', ')})`}
                  </Table.Td>
                  <Table.Td>
                    {param.default === undefined || param.default === null ? '—' : String(param.default)}
                  </Table.Td>
                  <Table.Td>{param.description}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Stack>
    </Stack>
  );
}
