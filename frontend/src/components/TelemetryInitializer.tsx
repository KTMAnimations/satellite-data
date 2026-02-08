import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { telemetry } from '../services/telemetry';

export function TelemetryInitializer() {
  const location = useLocation();
  const prevPathRef = useRef<string | null>(null);

  const path = `${location.pathname}${location.search}`;

  useEffect(() => {
    telemetry.setCurrentPath(path);
  }, [path]);

  useEffect(() => {
    telemetry.init();
  }, []);

  useEffect(() => {
    if (prevPathRef.current === null) {
      telemetry.log('page_load', { path });
      prevPathRef.current = path;
      return;
    }

    if (prevPathRef.current !== path) {
      telemetry.log('navigate', { from: prevPathRef.current, to: path });
      prevPathRef.current = path;
    }
  }, [path]);

  return null;
}

