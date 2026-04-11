import { Router } from 'express';
import { createPdf, getAssessment, updateAssessment, upsertObservation } from '../controllers/assessment.controller.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.get('/:id', requireAuth, getAssessment);
router.patch('/:id', requireAuth, updateAssessment);
router.post('/observation', requireAuth, upsertObservation);
router.get('/:id/pdf', requireAuth, createPdf);
export default router;
