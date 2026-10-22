import { createBrowserRouter, type RouteObject } from 'react-router';

import { ChangePasswordPage } from '../features/auth/ChangePasswordPage';
import { RequireAdmin, RequireAuth } from '../features/auth/guards';
import { LoginPage } from '../features/auth/LoginPage';
import { HomePage } from '../features/health/HomePage';
import { Layout } from './Layout';
import { NotFoundPage } from './NotFoundPage';

// `/login` queda fuera del layout; el resto exige sesión. Las secciones de cada fase se añaden como hijas de
// Layout y se cargan con `lazy` para dividir el bundle.
export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/',
        element: <Layout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: 'account/password', element: <ChangePasswordPage /> },
          {
            path: 'engines',
            lazy: async () => ({ Component: (await import('../features/engines/EnginesPage')).EnginesPage }),
          },
          {
            path: 'engines/:dbType',
            lazy: async () => ({
              Component: (await import('../features/engines/EngineDetailPage')).EngineDetailPage,
            }),
          },
          {
            path: 'projects',
            lazy: async () => ({
              Component: (await import('../features/projects/ProjectsPage')).ProjectsPage,
            }),
          },
          {
            path: 'projects/:projectId',
            lazy: async () => ({
              Component: (await import('../features/projects/ProjectDetailPage')).ProjectDetailPage,
            }),
          },
          {
            path: 'runs',
            lazy: async () => ({
              Component: (await import('../features/runs/RunsPage')).RunsPage,
            }),
          },
          {
            path: 'runs/:runId',
            lazy: async () => ({
              Component: (await import('../features/runs/RunDetailPage')).RunDetailPage,
            }),
          },
          {
            path: 'connections',
            lazy: async () => ({
              Component: (await import('../features/connections/ConnectionsPage')).ConnectionsPage,
            }),
          },
          {
            path: 'connections/new',
            lazy: async () => ({
              Component: (await import('../features/connections/ConnectionFormPage')).NewConnectionPage,
            }),
          },
          {
            path: 'connections/:connectionId',
            lazy: async () => ({
              Component: (await import('../features/connections/ConnectionDetailPage')).ConnectionDetailPage,
            }),
          },
          {
            path: 'connections/:connectionId/edit',
            lazy: async () => ({
              Component: (await import('../features/connections/ConnectionFormPage')).EditConnectionPage,
            }),
          },
          {
            path: 'admin',
            element: <RequireAdmin />,
            children: [
              {
                path: 'users',
                lazy: async () => ({ Component: (await import('../features/admin/UsersPage')).UsersPage }),
              },
              {
                path: 'sessions',
                lazy: async () => ({
                  Component: (await import('../features/admin/SessionsPage')).SessionsPage,
                }),
              },
              {
                path: 'allowlist',
                lazy: async () => ({
                  Component: (await import('../features/admin/AllowlistPage')).AllowlistPage,
                }),
              },
              {
                path: 'audit',
                lazy: async () => ({ Component: (await import('../features/admin/AuditPage')).AuditPage }),
              },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
