import React from 'react';

export type IconName =
  | 'arrow'
  | 'down'
  | 'grid'
  | 'chart'
  | 'flask'
  | 'activity'
  | 'sliders'
  | 'database'
  | 'shield'
  | 'lock'
  | 'wallet'
  | 'vault'
  | 'clock'
  | 'download'
  | 'upload'
  | 'refresh'
  | 'check'
  | 'info'
  | 'play'
  | 'menu'
  | 'chevron'
  | 'file'
  | 'pause'
  | 'close';

export const iconPaths: Record<string, string> = {
  close: 'M6 6l12 12M6 18 18 6',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  down: 'M12 4v16m-5-5 5 5 5-5',
  grid: 'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',
  chart: 'M3 3v18h18M6 15l5-5 4 3 6-8',
  flask: 'M9 3h6M10 3v6L4 19q-1 2 2 2h12q3 0 2-2L14 9V3M8 14h8',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  sliders: 'M4 7h16M4 17h16M8 4v6m8 4v6',
  database: 'M20 5c0 4-16 4-16 0s16-4 16 0v14c0 4-16 4-16 0V5m0 7c0 4 16 4 16 0',
  shield: 'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5zm7 4v3',
  wallet: 'M20 7H4V4h14v3M4 7v13h17V7m0 4h-6v5h6',
  vault: 'M4 3h16v18H4zM16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0m-4-4v8m-4-4h8',
  clock: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 7v5l3 2',
  download: 'M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5',
  upload: 'M12 16V4m-4 4 4-4 4 4M4 16v5h16v-5',
  refresh: 'M20 7V3m0 4h-4M4 17v4m0-4h4M5 8a8 8 0 0 1 14-3m0 11A8 8 0 0 1 5 19',
  check: 'M5 12l4 4L19 6',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 11v6m0-10v1',
  play: 'm8 4 12 8-12 8z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  chevron: 'm9 5 7 7-7 7',
  file: 'M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h6',
  pause: 'M8 4v16M16 4v16'
};

interface IconProps {
  name: IconName | string;
  className?: string;
}

export const Icon: React.FC<IconProps> = ({ name, className = 'icon' }) => {
  const d = iconPaths[name] || iconPaths.arrow;
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d={d} />
    </svg>
  );
};
