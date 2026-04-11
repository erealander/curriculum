import { Router } from 'express';
import { importWorkizAppointment, listWorkizAppointments } from '../controllers/workiz.controller.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.get('/appointments', requireAuth, listWorkizAppointments);
router.post('/appointments/:appointmentId/import', requireAuth, importWorkizAppointment);
export default router;
