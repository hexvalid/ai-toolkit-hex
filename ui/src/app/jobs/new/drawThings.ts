import { DrawThingsServerModel, SelectOption } from '@/types';

export const drawThingsSamplerOptions: SelectOption[] = [
  { value: 'DPM++ 2M Karras', label: 'DPM++ 2M Karras' },
  { value: 'Euler A', label: 'Euler A' },
  { value: 'DDIM', label: 'DDIM' },
  { value: 'PLMS', label: 'PLMS' },
  { value: 'DPM++ SDE Karras', label: 'DPM++ SDE Karras' },
  { value: 'UniPC', label: 'UniPC' },
  { value: 'LCM', label: 'LCM' },
  { value: 'Euler A Substep', label: 'Euler A Substep' },
  { value: 'DPM++ SDE Substep', label: 'DPM++ SDE Substep' },
  { value: 'TCD', label: 'TCD' },
  { value: 'Euler A Trailing', label: 'Euler A Trailing' },
  { value: 'DPM++ SDE Trailing', label: 'DPM++ SDE Trailing' },
  { value: 'DPM++ 2M AYS', label: 'DPM++ 2M AYS' },
  { value: 'Euler A AYS', label: 'Euler A AYS' },
  { value: 'DPM++ SDE AYS', label: 'DPM++ SDE AYS' },
  { value: 'DPM++ 2M Trailing', label: 'DPM++ 2M Trailing' },
  { value: 'DDIM Trailing', label: 'DDIM Trailing' },
  { value: 'UniPC Trailing', label: 'UniPC Trailing' },
  { value: 'UniPC AYS', label: 'UniPC AYS' },
];

export const drawThingsSeedModeOptions: SelectOption[] = [
  { value: 'Legacy', label: 'Legacy' },
  { value: 'TorchCpuCompatible', label: 'Torch CPU Compatible' },
  { value: 'ScaleAlike', label: 'Scale Alike' },
  { value: 'NvidiaGpuCompatible', label: 'NVIDIA GPU Compatible' },
];

export const drawThingsDefaultSampler = 'DPM++ 2M Karras';

export const defaultDrawThingsSampleConfig = {
  server: 'localhost',
  port: 7859,
  use_tls: true,
  shared_secret: '',
  model: '',
  seed_mode: 'ScaleAlike',
  clip_skip: 1,
  lora_mode: 'All',
};

export function getDrawThingsModelOptions(models: DrawThingsServerModel[], currentModel: string): SelectOption[] {
  const options = [...models]
    .filter(model => typeof model.file === 'string' && model.file.trim() !== '')
    .map(model => {
      const fileName = model.file.trim();
      const modelName = (model.name || '').trim();
      return {
        value: fileName,
        label: modelName !== '' && modelName !== fileName ? `${modelName} (${fileName})` : fileName,
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));

  const normalizedCurrentModel = currentModel.trim();
  if (normalizedCurrentModel !== '' && !options.some(option => option.value === normalizedCurrentModel)) {
    options.unshift({
      value: normalizedCurrentModel,
      label: `${normalizedCurrentModel} (Current Value)`,
    });
  }

  return options;
}
