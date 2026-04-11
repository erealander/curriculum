import { Router } from 'express';
import authRoutes from './auth.routes.js';
import workizRoutes from './workiz.routes.js';
import assessmentRoutes from './assessment.routes.js';
import tagsRoutes from './tags.routes.js';
import settingsRoutes from './settings.routes.js';

const router = Router();
router.use('/auth', authRoutes);
router.use('/workiz', workizRoutes);
router.use('/assessments', assessmentRoutes);
router.use('/tags', tagsRoutes);
router.use('/settings', settingsRoutes);

export default router;
