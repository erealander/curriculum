import { Router } from 'express';
import { getSettings, upsertSettings } from '../controllers/settings.controller.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.get('/', requireAuth, getSettings);
router.put('/', requireAuth, upsertSettings);
export default router;
