import { MantineProvider } from '@mantine/core';
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { colorSchemeManager } from './colorScheme';
import { createQueryClient } from './queryClient';
import { theme } from './theme';

interface ProvidersProps {
  children: ReactNode;
  queryClient?: QueryClient;
  /** Clases `hiddenFrom`/`visibleFrom` de Mantine. Las pruebas las desactivan: jsdom 31 evalúa sus `@media` con
   * una ventana de 1024 px y daría por ocultos los controles de móvil. */
  withGlobalClasses?: boolean;
}

export function Providers({ children, queryClient, withGlobalClasses = true }: ProvidersProps) {
  const [client] = useState(() => queryClient ?? createQueryClient());
  return (
    <MantineProvider
      theme={theme}
      defaultColorScheme="auto"
      colorSchemeManager={colorSchemeManager}
      withGlobalClasses={withGlobalClasses}
    >
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </MantineProvider>
  );
}
