import { useEffect, useState } from 'react';

export const PUBLIC_ROUTES = [
  'home',
  'method',
  'login',
  'register'
] as const;

export const PROTECTED_ROUTES = [
  'overview',
  'forecast',
  'scenarios',
  'investments',
  'events',
  'decisions',
  'activity',
  'policy',
  'data'
] as const;

export const VALID_ROUTES = [
  ...PUBLIC_ROUTES,
  ...PROTECTED_ROUTES
] as const;

export type RouteId = (typeof VALID_ROUTES)[number];
export type PublicRouteId = (typeof PUBLIC_ROUTES)[number];
export type ProtectedRouteId = (typeof PROTECTED_ROUTES)[number];

export const isPublicRoute = (route: string): route is PublicRouteId =>
  PUBLIC_ROUTES.includes(route as PublicRouteId);

export const isProtectedRoute = (route: string): route is ProtectedRouteId =>
  PROTECTED_ROUTES.includes(route as ProtectedRouteId);

const ROUTE_TITLES: Record<string, string> = {
  login: 'Sign In',
  register: 'Create Banker Account',
  overview: 'Overview',
  forecast: 'Cashflow forecast',
  scenarios: 'Scenario lab',
  investments: 'Investment options',
  events: 'Payments & events',
  decisions: 'Decision history',
  activity: 'Sweep activity',
  policy: 'Reserve policy',
  data: 'Data sources'
};

const normalizeHash = (hash: string): RouteId => {
  const clean = hash.replace(/^#\/?/, '').trim();
  if (!clean) return 'home';
  if (VALID_ROUTES.includes(clean as RouteId)) {
    return clean as RouteId;
  }
  return 'home';
};

export const useHashRoute = () => {
  const [route, setRoute] = useState<RouteId>(() => {
    return normalizeHash(window.location.hash);
  });

  useEffect(() => {
    const handleHashChange = () => {
      const clean = window.location.hash.replace(/^#\/?/, '').trim();
      if (clean && !VALID_ROUTES.includes(clean as RouteId)) {
        window.location.hash = 'home';
        return;
      }
      const current = normalizeHash(window.location.hash);
      setRoute(current);
      if (current !== 'method') {
        window.scrollTo(0, 0);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    // Initial validation: if invalid hash was present, normalize to home
    const raw = window.location.hash.replace(/^#\/?/, '').trim();
    if (raw && !VALID_ROUTES.includes(raw as RouteId)) {
      window.location.hash = 'home';
    }

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    if (route === 'home' || route === 'method') {
      document.title = 'Reserve Juggler — Every rupee, in its right place.';
    } else {
      const title = ROUTE_TITLES[route] || 'Workspace';
      document.title = `${title} · Reserve Juggler`;
    }
  }, [route]);

  const scrollToMethod = (e: React.MouseEvent) => {
    e.preventDefault();
    const elem = document.getElementById('method');
    if (elem) {
      elem.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'instant'
          : 'smooth'
      });
    }
  };

  return { route, setRoute, scrollToMethod };
};
