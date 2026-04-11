import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import routes from './routes/index.js';
import { env } from './config/env.js';

const app = express();
app.use(cors());
app.use(express.json({ limit: '5mb' }));

const storagePath = path.resolve(env.STORAGE_DIR);
if (!fs.existsSync(storagePath)) fs.mkdirSync(storagePath, { recursive: true });
app.use('/uploads', express.static(storagePath));

app.get('/health', (_, res) => res.json({ status: 'ok' }));
app.use('/api', routes);

app.listen(env.PORT, () => {
  console.log(`server listening on ${env.PORT}`);
});
