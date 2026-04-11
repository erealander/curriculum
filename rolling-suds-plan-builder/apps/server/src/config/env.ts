import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const schema = z.object({
  NODE_ENV: z.string().default('development'),
  PORT: z.coerce.number().default(4000),
  DATABASE_URL: z.string().min(1),
  JWT_SECRET: z.string().min(12),
  WORKIZ_MODE: z.enum(['mock', 'api']).default('mock'),
  WORKIZ_API_BASE_URL: z.string().optional(),
  WORKIZ_API_KEY: z.string().optional(),
  STORAGE_DIR: z.string().default('uploads'),
  PUBLIC_BASE_URL: z.string().default('http://localhost:4000')
});

export const env = schema.parse(process.env);
