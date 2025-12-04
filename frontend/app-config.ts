import type { AppConfig } from './lib/types';

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'E-commerce',
  pageTitle: 'E-commerce agent demo',
  pageDescription: 'Test different e-commerce voice agents with live interaction',

  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  logo: '/lk-logo.svg',
  accent: '#FFD700',
  logoDark: '/lk-logo-dark.svg',
  accentDark: '#FFD700',
  startButtonText: 'Start Call',

  agentName: undefined,
};
