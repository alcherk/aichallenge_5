// Settings and configuration types

export type ModelName =
  | 'gpt-4o'
  | 'gpt-4-turbo'
  | 'gpt-4'
  | 'gpt-4o-mini'
  | 'gpt-3.5-turbo';

export interface ModelPricing {
  input: number;  // per 1M tokens
  output: number; // per 1M tokens
}

export interface Settings {
  systemPrompt: string;
  temperature: number;
  model: ModelName;
  compressionThreshold: number;
}

export const DEFAULT_SYSTEM_PROMPT = `Ты помощник-прокси между пользователем и системой.

Твоя задача — сначала ПОНЯТЬ задачу, а потом решать.

Формат ответа: обычный текст или Markdown.

Если информации недостаточно, задай уточняющие вопросы.

Если информации достаточно и можно решить задачу, предоставь подробное решение.

Правила:
- Не придумывай ответ на задачу, если нет данных — сперва задавай вопросы.
- Когда считаешь, что вопросов достаточно, предоставь итоговый ответ.
- Используй Markdown для форматирования (заголовки, списки, код и т.д.).`;

export const DEFAULT_SETTINGS: Settings = {
  systemPrompt: DEFAULT_SYSTEM_PROMPT,
  temperature: 0.7,
  model: 'gpt-4o-mini',
  compressionThreshold: 10,
};

export const MODEL_PRICING: Record<ModelName, ModelPricing> = {
  'gpt-4o': { input: 2.50, output: 10.00 },
  'gpt-4-turbo': { input: 10.00, output: 30.00 },
  'gpt-4': { input: 30.00, output: 60.00 },
  'gpt-4o-mini': { input: 0.15, output: 0.60 },
  'gpt-3.5-turbo': { input: 0.50, output: 1.50 },
};

export const CONTEXT_WINDOWS: Record<ModelName, number> = {
  'gpt-4o': 128000,
  'gpt-4-turbo': 128000,
  'gpt-4': 8192,
  'gpt-4o-mini': 128000,
  'gpt-3.5-turbo': 16385,
};
